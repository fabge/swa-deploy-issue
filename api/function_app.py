from functools import cache
import logging
import json
import asyncio
from typing import Any

import azure.functions as func
from azurefunctions.extensions.http.fastapi import Request, StreamingResponse
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_core.tools import tool
from langgraph.graph import MessagesState, StateGraph
from langgraph.graph import END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.state import CompiledStateGraph

app = func.FunctionApp()

@cache
def setup_rag_graph() -> CompiledStateGraph:
    logging.info('Setting up RAG graph...')

    llm: AzureChatOpenAI = AzureChatOpenAI(
        azure_endpoint='https://gpt4-test-1p.openai.azure.com/',
        azure_deployment='gpt-4',
        api_version='2024-10-21',
    )

    embeddings: AzureOpenAIEmbeddings = AzureOpenAIEmbeddings(
        azure_endpoint='https://gpt4-test-1p.openai.azure.com/',
        azure_deployment='text-embedding-ada-002',
        api_version='2023-05-15',
    )

    logging.info('Loading vector store...')
    vector_store: FAISS = FAISS.load_local('storage', embeddings, allow_dangerous_deserialization=True)

    # Set up the graph
    graph_builder: StateGraph = StateGraph(MessagesState)

    # Define retrieval tool
    @tool(response_format='content_and_artifact')
    def retrieve(query: str) -> tuple[str, list]:
        '''Retrieve information related to a query.'''
        logging.info(f'Retrieving documents for query')
        retrieved_docs: list = vector_store.similarity_search(query, k=2)
        serialized: str = '\n\n'.join(
            (f'Source: {doc.metadata}\n' f'Content: {doc.page_content}')
            for doc in retrieved_docs
        )
        return serialized, retrieved_docs

    # Define the query or respond node
    def query_or_respond(state: MessagesState) -> dict[str, list]:
        '''Generate tool call for retrieval or respond.'''
        logging.info('Querying or responding...')
        llm_with_tools = llm.bind_tools([retrieve])
        response = llm_with_tools.invoke(state['messages'])
        return {'messages': [response]}

    # Define the tool node
    tools: ToolNode = ToolNode([retrieve])

    # Define the generate response node
    def generate(state: MessagesState) -> dict[str, list]:
        '''Generate answer.'''
        logging.info('Generating response...')
        # Get generated ToolMessages
        recent_tool_messages: list = []
        for message in reversed(state['messages']):
            if message.type == 'tool':
                recent_tool_messages.append(message)
            else:
                break
        tool_messages: list = recent_tool_messages[::-1]

        docs_content: str = '\n\n'.join(doc.content for doc in tool_messages)
        system_message_content: str = (
            'Du bist ein kompetenter und professioneller Support Mitarbeiter im Team One Platform (1P), '
            'welches Cloud Accounts and Developer Tooling innerhalb des Unternehmens EnBW AG anbietet. '
            'Einer unserer User hat eine Chat Nachricht geschrieben, nutze den folgenden Kontext um die Frage am Ende zu beantworten. '
            'Wenn Du die Antwort nicht weißt, sag einfach, dass Du es nicht weißt, versuche nicht, eine Antwort zu erfinden. '
            'Beantworte die Frage per Du.'
            '\n\n'
            f'{docs_content}'
        )

        conversation_messages: list = [
            message
            for message in state['messages']
            if message.type in ('human', 'system')
            or (message.type == 'ai' and not message.tool_calls)
        ]
        prompt: list = [SystemMessage(content=system_message_content)] + conversation_messages

        # Run
        response: BaseMessage = llm.invoke(prompt)
        return {'messages': [response]}

    # Build the graph
    graph_builder.add_node(query_or_respond)
    graph_builder.add_node(tools)
    graph_builder.add_node(generate)

    graph_builder.set_entry_point('query_or_respond')
    graph_builder.add_conditional_edges(
        'query_or_respond',
        tools_condition,
        {END: END, 'tools': 'tools'},
    )
    graph_builder.add_edge('tools', 'generate')
    graph_builder.add_edge('generate', END)

    compiled_graph = graph_builder.compile()
    logging.info('RAG graph setup completed')
    return compiled_graph


@app.route(route='message', methods=['POST'])
async def message(req: Request) -> StreamingResponse:
    logging.info('Received message request')

    # Get JSON data from the request
    body: dict[str, Any] = await req.json()
    message_text: str = str(body.get('text', ''))
    message_history: list[str] = [str(msg) for msg in body.get('messages', [])]

    # Convert to LangGraph format
    messages: list[BaseMessage] = []
    for message in message_history:
        if message.startswith('bot:'):
            messages.append(AIMessage(content=message[4:]))
        elif message.startswith('user:'):
            messages.append(HumanMessage(content=message[5:]))

    # Add the current message
    messages.append(HumanMessage(content=message_text))
    logging.info('Processing message')

    # Set up the model and get the response
    graph: CompiledStateGraph = setup_rag_graph()

    async def stream_response():
        sources: list[str] = []
        logging.info('Starting response streaming...')
        async for chunk in graph.astream({'messages': messages}, stream_mode='messages'):
            message, metadata = chunk

            # Collect sources from tool messages
            if isinstance(message, BaseMessage) and hasattr(message, 'artifact') and message.artifact:
                for doc in message.artifact:
                    if hasattr(doc, 'metadata') and 'source' in doc.metadata:
                        url = f"https://oneplatform.enbw.com{doc.metadata['source'][4:].replace('index.md', '').replace('.md', '')}"
                        sources.append(f'<a href="{url}">{url}</a>')

            if isinstance(message, AIMessage):
                response_data = {
                    'id': len(message_history) + 1,
                    'from': 'bot',
                    'text': message.content
                }
                # Format as SSE event
                yield f"data: {json.dumps(response_data)}\n\n"
                # Add a small delay to ensure chunks are sent
                await asyncio.sleep(0.05)

        # After all chunks, if we have sources, send them as a final chunk
        if sources:
            response_data = {
                'id': len(message_history) + 1,
                'from': 'bot',
                'text': f'\n\nRelevante Quellen:\n{chr(10).join(sources)}'
            }
            # Format as SSE event
            yield f"data: {json.dumps(response_data)}\n\n"
            # Add a small delay to ensure the final chunk is sent
            await asyncio.sleep(0.1)

        logging.info('Response completed')
        if isinstance(message, AIMessage):
            logging.info(
                json.dumps({
                    'type': 'chatbot',
                    'message_id': len(message_history) + 1,
                    'answer': message.content + f'\n\nRelevante Quellen:\n{chr(10).join(sources)}'
                })
            )

    return StreamingResponse(
        stream_response(),
        headers={"Content-Type": "text/event-stream"},
    )
