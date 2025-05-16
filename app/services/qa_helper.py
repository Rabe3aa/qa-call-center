from app.config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, OPENAI_API_KEY, logger
import boto3, json, re, ast, os
import openai
import time



class QAHelper:
    def __init__(self, job_name, s3_uri, OutputBucketName, InputBucketName,
                 filename, filepath, qa_criteria_file):

        self.main_directory = os.path.abspath("reports")
        self.job_name = job_name
        self.s3_uri = s3_uri
        self.OutputBucketName = OutputBucketName
        self.InputBucketName = InputBucketName
        self.filename = filename
        self.filepath = filepath

        self.session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

        openai.api_key = OPENAI_API_KEY

        with open(qa_criteria_file, encoding='utf-8') as f:
            self.qa_criteria = json.load(f)

        self.s3_client = None

    def upload_file_aws(self):
        self.s3_client = self.session.client('s3')
        self.s3_client.upload_file(self.filepath, self.InputBucketName, self.filename)

    def get_transcription(self):
        transcribe_client = self.session.client('transcribe')

        transcribe_client.start_transcription_job(
            TranscriptionJobName=self.job_name,
            LanguageCode="ar-SA",
            MediaFormat="wav",
            Media={"MediaFileUri": self.s3_uri},
            Settings={
                "ShowSpeakerLabels": True,
                "MaxSpeakerLabels": 2,
                "ShowAlternatives": False
            },
            OutputBucketName=self.OutputBucketName
        )

        max_retries = 20
        sleep_time = 5

        for _ in range(max_retries):
            result = transcribe_client.get_transcription_job(TranscriptionJobName=self.job_name)
            status = result['TranscriptionJob']['TranscriptionJobStatus']
            if status in ['COMPLETED', 'FAILED']:
                break
            time.sleep(sleep_time)
            sleep_time *= 1.2
        else:
            raise TimeoutError("Transcription job took too long.")

        response = self.s3_client.get_object(Bucket=self.OutputBucketName, Key=f'{self.job_name}.json')
        content = response['Body'].read().decode('utf-8')
        data = json.loads(content)

        return [(i['transcript'], i['speaker_label']) for i in data['results']['audio_segments']]

    def format_transcript_for_prompt(self, transcript):
        return "\n".join([f"{speaker}: {text}" for text, speaker in transcript])

    def correct_transcript(self, transcript, model):
        formatted = self.format_transcript_for_prompt(transcript)

        prompt = f"""
        You are an expert in understanding Egyptian Arabic. The following transcript is from a phone call between a customer and a call center agent. The transcription was done by a speech-to-text model and may contain errors such as incorrect words or misheard phrases.

        Your job is to correct the transcription by:
        - Fixing words that are clearly wrong (e.g. “تلات حبان” should be “تلات حمام”).
        - Keeping the meaning and flow natural.
        - DO NOT invent new content.
        - Keep the speaker labels exactly the same (spk_0 for agent, spk_1 for customer).

        Transcript:
        {formatted}

        Return the corrected transcript in the format: a list of Python tuples like:
        [("text", "spk_0"), ("text", "spk_1"), ...]
        """

        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that corrects Arabic transcripts."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        return response['choices'][0]['message']['content']

    def parse_transcript_from_code_block_string(self, text_output):
        code_block = re.sub(r"^```python\s*|\s*```$", "", text_output.strip(), flags=re.DOTALL)

        try:
            transcript = ast.literal_eval(code_block)
            if isinstance(transcript, list) and all(isinstance(t, tuple) and len(t) == 2 for t in transcript):
                return transcript
        except Exception as e:
            logger.warning(f"Failed to parse transcript: {e}")
        return []

    def generate_summary(self, transcript_tuples, model):
        prompt_template = """
        You are a Call Center Quality Assistant.

        Below is a corrected transcript of a phone call between a customer (spk_1) and a call center agent (spk_0). Your job is to summarize ONLY the agent’s behavior (spk_0) in 7 bullet points.

        Focus on the following aspects:
        1. Did the agent collect customer details (e.g., name, location)?
        2. Did the agent offer upselling or suggest additional units, locations, or features?
        3. Did the agent greet the caller politely? Did they close the call well?
        4. Was the tone professional, friendly, and confident?
        5. Did the agent actively listen and engage with the customer’s concerns?
        6. Did the agent use slang or informal words?
        7. Did the agent offer or gather additional useful information?

        ### Transcript:
        {transcript}

        ### Summary of Agent Behavior:
        """

        formatted_transcript = "\n".join([f"{speaker}: {text}" for text, speaker in transcript_tuples])
        prompt = prompt_template.format(transcript=formatted_transcript)

        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a call center QA assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        return response['choices'][0]['message']['content']

    def score_criteria(self, summary_text, criteria_dict, model):
        prompt_template = """
        You are a QA scoring assistant for Egyptian Arabic call centers.

        Your task is to evaluate the following criterion based on the agent’s behavior described in the summary.

        ### Criterion:
        {criterion_description}

        ### Summary of Agent Behavior:
        {summary}

        Return only one of: PASS, FAIL, or N/A.
        """

        results = {}
        for criterion, description in criteria_dict.items():
            prompt = prompt_template.format(criterion_description=description, summary=summary_text)

            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a QA agent who strictly outputs PASS, FAIL, or N/A."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )

            decision = response['choices'][0]['message']['content'].strip().upper()
            results[criterion] = decision if decision in ["PASS", "FAIL", "N/A"] else "N/A"

        return results

    def extract_json_from_response(self, response_text):
        try:
            match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(response_text.strip())
        except Exception:
            return None

    def generate_feedback(self, summary, scores, criteria_dict, model="gpt-4o"):
        prompt_template = """
        You are a QA evaluation assistant for Egyptian Arabic call centers.

        Given the summary of an agent’s behavior and the score of a specific criterion, provide:
        1. A short explanation why the score was given.
        2. A suggestion (if the score is not PASS) on how the agent could improve.

        ### Criterion:
        {criterion_name}: {criterion_description}

        ### Summary of Agent Behavior:
        {summary}

        ### Score: {score}

        Respond in this JSON format:
        {{
          "score": "{score}",
          "explanation": "...",
          "suggestion": "..."  # empty string if score is PASS
        }}
        """

        feedback_results = {}

        for criterion, score in scores.items():
            description = criteria_dict[criterion]
            prompt = prompt_template.format(
                criterion_name=criterion,
                criterion_description=description,
                summary=summary,
                score=score
            )

            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a QA evaluator that explains scores and gives helpful suggestions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            content = response['choices'][0]['message']['content']
            feedback = self.extract_json_from_response(content)

            if not feedback:
                logger.warning(f"⚠️ Failed to parse feedback for: {criterion}\nGPT response:\n{content}")
                feedback = {
                    "score": score,
                    "explanation": "Could not generate explanation.",
                    "suggestion": "" if score == "PASS" else "Please clarify and expand on this criterion next time."
                }

            feedback_results[criterion] = feedback

        return feedback_results

    def save_report(self, report_dict, company_id, call_id):
        save_path = f"{self.main_directory}/{company_id}/{call_id}"
        os.makedirs(save_path, exist_ok=True)
        with open(f"{save_path}/report.json", "w", encoding='utf-8') as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)

    def run_pipeline(self, model="gpt-4o", company_id="default", call_id="default"):
        logger.info("📤 Uploading audio file to S3...")
        self.upload_file_aws()

        logger.info("🗣️ Getting diarized transcript from Transcribe...")
        raw_transcript = self.get_transcription()

        logger.info("🛠️ Correcting transcript using GPT...")
        corrected_text = self.correct_transcript(raw_transcript, model=model)

        logger.info("🔍 Parsing corrected transcript...")
        corrected_transcript = self.parse_transcript_from_code_block_string(corrected_text)
        if not corrected_transcript:
            logger.warning("⚠️ Failed to parse transcript. Exiting.")
            return None

        logger.info("📄 Generating agent behavior summary...")
        summary = self.generate_summary(corrected_transcript, model=model)
        logger.info(f"📝 Summary:\n{summary}")

        logger.info("✅ Scoring agent performance...")
        scores = self.score_criteria(summary, self.qa_criteria, model=model)

        logger.info("💡 Generating evaluation feedback...")
        feedback = self.generate_feedback(summary, scores, self.qa_criteria, model=model)

        final_result = {
            "summary": summary,
            "scores": scores,
            "feedback": feedback
        }

        self.save_report(final_result, company_id, call_id)
        logger.info("✅ QA Pipeline completed successfully.")

        return final_result