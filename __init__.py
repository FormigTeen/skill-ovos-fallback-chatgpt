from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.skills.fallback import FallbackSkill
from ovos_config import Configuration
from openai import OpenAI

class ChatGPTSkill(FallbackSkill):

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(
            internet_before_load=True,
            network_before_load=True,
            requires_internet=True,
            requires_network=True,
        )

    def initialize(self):
        self.add_event("speak", self.handle_speak)
        self.add_event("recognizer_loop:utterance", self.handle_utterance)
        self.register_fallback(self.ask_chatgpt, 85)

    @property
    def config(self):
        return Configuration().get('chatgpt' ,{})

    @property
    def ai_name(self):
        return self.config.get("name", "Chat G.P.T.")

    @property
    def confirmation(self):
        return self.config.get("confirmation", False)

    @property
    def key(self):
        return self.config.get("key")

    @property
    def thread_id(self):
        return self.config.get("thread_id")

    @property
    def assistant_id(self):
        return self.config.get("assistant_id")

    @property
    def client(self):
        """created fresh to allow key/url rotation when settings.json is edited"""
        try:
            return OpenAI(
                api_key=self.key
            )
        except Exception as err:
            self.log.error(err)
            return None

    @property
    def chat(self):
        try:
            return self.client.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant_id,
                stream=True
            )
        except Exception as err:
            self.log.error(err)
            return None

    def handle_utterance(self, message):
        utt = message.data.get("utterance")
        #print(utt)
        #self.create_message(utt, role="user")

    def handle_speak(self, message):
        utt = message.data.get("utterance")
        print(message.data)
        ##self.create_message(utt, role="ovos-ai")

    def create_message(self, message, role):
        if "key" not in self.config or "assistant_id" not in self.config or "thread_id" not in self.config:
            self.log.error(
                "ChatGPT not configured yet, please set your API key in settings.json",
            )
        return self.client.beta.threads.messages.create(
            self.thread_id,
            role=role,
            content=message
        )
    def _async_ask(self, message):
        utterance = message.data["utterance"]
        self.create_message(utterance, role="user")
        answered = False
        try:
            for chunk in self.chat:
                if chunk:
                    if chunk.event == "thread.run.completed":
                        answered = True
                    if chunk.event == "thread.message.completed":
                        answered = True
                        for message in chunk.data.content:
                            None
                            self.speak(message.text.value)
                    if chunk.event == "thread.run.failed":
                        raise Exception("Error on server")
        except Exception as err:  # speak error on any network issue / no credits etc
            self.log.error(err)
        if not answered:
            self.speak_dialog("gpt_error", data={"name": self.ai_name})

    def ask_chatgpt(self, message):
        utterance = message.data["utterance"]
        if "key" not in self.config or "assistant_id" not in self.config or "thread_id" not in self.config:
            self.log.error(
                "ChatGPT not configured yet, please set your API key in settings.json",
            )
            return False  # ChatGPT not configured yet
        if self.confirmation:
            self.speak_dialog("asking", data={"name": self.ai_name})
        # ask in a thread so fallback doesnt timeout
        self.bus.once("async.chatgpt.fallback", self._async_ask)
        self.bus.emit(
            message.forward("async.chatgpt.fallback", {"utterance": utterance})
        )
        return True
