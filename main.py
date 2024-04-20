from openai import OpenAI
from typing_extensions import override
from openai import AssistantEventHandler

client = OpenAI()
assistant = None
vector_store = None
questions = None


def ini():

    global assistant

    assistant = client.beta.assistants.create(
        name="Asistente de reglamento del condominio",
        instructions="Asistente de reglamento del condominio, responde con exactitud las preguntas relacionadas con el reglamento del condominio",
        model="gpt-4-turbo",
        tools=[{"type": "file_search"}],
    )


def check_vector_store():
    # Check if the vector store already exists
    global vector_store
    vector_store = client.beta.vector_stores.list()
    if vector_store.data:
        vector_store = vector_store.data[0]
        print("Vector store already exists, using existing vector store")
    else:
        vector_store = client.beta.vector_stores.create(
            name="Reglamento del condominio"
        )
        print("Vector store created")

        # Ready the files for upload to OpenAI
        file_paths = ["reglamento.docx"]
        file_streams = [open(path, "rb") for path in file_paths]

        # Use the upload and poll SDK helper to upload the files, add them to the vector store,
        # and poll the status of the file batch for completion.
        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=file_streams
        )

        # You can print the status and the file counts of the batch to see the result of this operation.
        print(file_batch.status)
        print(file_batch.file_counts)


def tell_assistant_to_use_vector_store():
    global vector_store
    global assistant
    assistant = client.beta.assistants.update(
        assistant_id=assistant.id,
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )


class EventHandler(AssistantEventHandler):
    @override
    def on_text_created(self, text) -> None:
        print(f"\nassistant > ", end="", flush=True)

    @override
    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    @override
    def on_message_done(self, message) -> None:
        # print a citation to the file searched
        message_content = message.content[0].text
        annotations = message_content.annotations
        citations = []
        for index, annotation in enumerate(annotations):
            message_content.value = message_content.value.replace(
                annotation.text, f"[{index}]"
            )
            if file_citation := getattr(annotation, "file_citation", None):
                cited_file = client.files.retrieve(file_citation.file_id)
                citations.append(f"[{index}] {cited_file.filename}")

        print(message_content.value)
        print("\n".join(citations))


# Then, we use the stream SDK helper
# with the EventHandler class to create the Run
# and stream the response.
def run_assistant():
    global assistant
    global client
    thread = client.beta.threads.create()
    my_thread_message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="Cuando se puede hacer fiestas en el condominio?",
    )
    with client.beta.threads.runs.stream(
        thread_id=thread.id,
        assistant_id=assistant.id,
        instructions="Asistente de reglamento del condominio, responde con exactitud las preguntas relacionadas con el reglamento del condominio",
        event_handler=EventHandler(),
    ) as stream:
        stream.until_done()


def main():
    ini()
    check_vector_store()
    tell_assistant_to_use_vector_store()
    run_assistant()


if __name__ == "__main__":
    main()
