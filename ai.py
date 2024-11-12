import time
from openai import OpenAI
import os
import configparser
import re

config = configparser.ConfigParser()
config.read('config.cfg')
KEY = config.get('OpenAIAPI', 'key').strip('"')
ASSID = config.get('OpenAIAPI', 'assistant_id').strip('"')

class Ai:
    def __init__(self):
        self.client = OpenAI(api_key=KEY)
        self.ASSISTANT_ID = ASSID

    def ask(self, domanda):
        os.environ['OPENAI_API_KEY'] = KEY

        thread = self.client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": domanda,
                }
            ]
        )

        run = self.client.beta.threads.runs.create(thread_id=thread.id, assistant_id=self.ASSISTANT_ID)
        print(f"thread creato: {run.id}")

        while run.status != "completed":
            run = self.client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            print(f"stato: {run.status}")
            time.sleep(1)
        else:
            print(f"thread completato")

        message_response = self.client.beta.threads.messages.list(thread_id=thread.id)
        messages = message_response.data

        latest_message = messages[0]
        # Correzione dell'espressione regolare
        out = re.sub(r'【\d+(:\d+)?†source】', '', latest_message.content[0].text.value)
        return out