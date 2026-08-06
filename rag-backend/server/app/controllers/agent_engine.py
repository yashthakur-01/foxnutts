from typing import Optional
from langchain_core.runnables import configurable
from ast import operator
from langgraph.prebuilt import InjectedState
from langgraph.graph import StateGraph, START, END, add_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from typing import Literal,TypedDict, Annotated, Any
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode, tools_condition
import os
import operator
import time
import asyncio
from app.helper.obseravable_node import observable_node



_compiled_graph_instance = None
_compiled_model_instance = {}
_tools = None


load_dotenv()

def get_chat_model(provider: Literal["gemini", "openai", "groq"], model_name: str, temperature: float = 0.4, max_tokens: int = 512):
    if not provider or not model_name:
        raise ValueError("Both provider and model_name must be provided.")
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        return ChatGoogleGenerativeAI(model=model_name, temperature=temperature, max_tokens=max_tokens)
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        return ChatOpenAI(model=model_name, temperature=temperature, max_tokens=max_tokens)
    elif provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set.")
        return ChatOpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, model=model_name, temperature=temperature, max_tokens=max_tokens)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    

def get_model_instance(provider: Literal["gemini", "openai", "groq"], model_name: str, temperature: float = 0.4, max_tokens: int = 512):
    return get_chat_model(provider, model_name, temperature, max_tokens)
   
class ModelClass(TypedDict):
    provider: Literal["gemini", "openai", "groq"]
    model_name: str
    temperature: float
    max_tokens: int

class AgentState(TypedDict):
    system_prompt: str

    error_messages : Optional[Annotated[list[dict[str, str]],operator.add]]

    max_iter: int
    
    query: Annotated[list[str], operator.add]
    
    messages: Annotated[list[BaseMessage], add_messages]
    
    model: ModelClass

    remarks: str

    search_enabled: bool
    
    disclaimer: bool

    trajectory: Annotated[list[dict[str, str]], operator.add]

    current_context : str | None

    retrived_context: Annotated[list[str], operator.add]

    query_context_pairs: Annotated[list[dict[str, Any]], operator.add]
    
    query_type: str | None

    route: Annotated[list[str],operator.add]

class ConditionalRouterOutput(TypedDict):   
    route: Literal["generic_or_repetitive", "genuine_query","satisfactory", "unsatisfactory", "revise", "query_rephrase", "clarify"]


@observable_node("genuine_generic_router")
async def conditional_router_node_1(state: AgentState,config: RunnableConfig):
    """
    this is a conditional router that returns the response as generic_or_repetitive or genuine_query on 
    the basis of the query and chat history
    """
    state['trajectory']

    messages = state["messages"]
    provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    llm = get_model_instance(provider, model_name, temperature, max_tokens)
    if provider=='groq':
        llm = llm.with_structured_output(ConditionalRouterOutput, method="function_calling", include_raw=True)
    else:
        llm = llm.with_structured_output(ConditionalRouterOutput, include_raw=True)

    
    system_prompt = SystemMessage(content="""You are an intent classifier for an enterprise document search & RAG assistant. Classify the user's latest query:

CLASSIFICATION RULES:
1. 'generic_or_repetitive': Return ONLY for basic greetings, pleasantries, chit-chat, or identity questions.
   - Examples: "hello", "hi there", "how are you?", "thank you", "bye", "who created you?".

2. 'genuine_query': Return for ANY question about business, policies, procedures, compensation/salary, technical details, or document content, OR requests to expand/rephrase an answer.
   - Examples: "whats the monthly salary types", "what is the leave policy?", "explain section 3", "regenerate that answer with details".

3. DEFAULT RULE: If uncertain whether a question is generic vs document-related, ALWAYS choose 'genuine_query' to retrieve document context.

Output exactly one: 'generic_or_repetitive' or 'genuine_query'.""")
    
    full_messages = [system_prompt] + messages
    
    await asyncio.sleep(2.5)
    response = await llm.ainvoke(full_messages)

    parsed_output = response["parsed"]
    raw_message = response["raw"]

    return {"route": [parsed_output["route"]], "current_context": None, "node_output": [raw_message]}

@observable_node("context_retriver")
async def retrieve_context(state:AgentState, config: RunnableConfig):

    import importlib
    query_pipeline = importlib.import_module("app.controllers.2_query_pipeline")
    fetch_context_from_vector_db = query_pipeline.fetch_context_from_vector_db
    query=state["query"][-1]
    configurable = config.get("configurable", {})
    customerId = configurable.get("customerId", "")
    tenantId = configurable.get("tenantId", "")  # Retained for analytics/tracing
    workspaceId = configurable.get("workspaceId", "")
    similarityThreshold = float(configurable.get("similarityThreshold", 0.6))
    
    context = await fetch_context_from_vector_db(query, customerId, workspaceId, similarity_threshold=similarityThreshold)
    is_context_found = bool(context and context.strip())
    return {
        "retrived_context": [context],
        "current_context": context,
        "query_context_pairs": [{
            "query": query,
            "context_received": context,
            "context_found": is_context_found,
            "query_type": "genuine_query"
        }],
        "query_type": "genuine_query",
        "node_output": [context]
    }

@tool
async def web_search(state: Annotated[dict, InjectedState]) -> str:
    """Use this tool to search Google for up-to-date real-time information.
    
    parameters: (query: str): The search query string.
    
    returns: str: A formatted string of search results, including source URLs and content snippets. If the search fails, returns an error message.
    
    """
    from langchain_community.tools.tavily_search import TavilySearchResults
    query = state['query'][-1]
    tavily_engine = TavilySearchResults(max_results=3)
    try:
        results = await tavily_engine.ainvoke({"query": query})
        
        formatted_results = []
        for doc in results:
            formatted_results.append(f"Source: {doc['url']}\nContent: {doc['content']}\n---")
            
        return "\n".join(formatted_results)
        
    except Exception as e:
        return f"Search temporarily unavailable. Proceed with internal knowledge. Error: {str(e)}" 


# @tool
# def query_rephraser(notes: str,state: Annotated[dict, InjectedState], config: RunnableConfig):
#     '''this is a tool to rephrase the query, to enrich the query and improve the quality of the retrival.
#         parameters: 
#         notes: "some notes on how to improve the query, kinds of information that may be required, including different intents etc. give short 1-2 line suggestion"
#     '''
#     provider = state["model"]["provider"]
#     model_name = state["model"]["model_name"]
#     temperature = state["model"]["temperature"]
#     max_tokens = state["model"]["max_tokens"]
#     previous_query = state['query'][-1]
#     llm = get_model_instance(provider, model_name, temperature, max_tokens)

#     prompt = ChatPromptTemplate.from_template(
#         '''
#         you are an expert query rephraser. using the previous_query and the notes, you have to rephrase the query in a way that improves the quality of the retrival.

#         previous_query: {previous_query}
#         notes: {notes}

#         return only the new enriched query in response.
#         '''
#     )
#     result = (prompt | llm).invoke({previous_query: previous_query, notes: notes})
#     return {"query": [result.content]}
   

def route_after_chatbot(
    state: AgentState, config: RunnableConfig
) -> Literal["tools", "response_evaluation_node"]:
    
    last_message = state["messages"][-1]

    if (
        isinstance(last_message, AIMessage)
        and getattr(last_message, "tool_calls", None)
    ):
        return "tools"

    return "response_evaluation_node"       

@observable_node("chatbot_node")
async def chatbot_node(state: AgentState, config: RunnableConfig):
    """
    Dynamically initializes the selected LLM provider, applies system prompts,
    and binds tools entirely based on runtime configuration passed by the backend.
    """
    
    model_provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    system_prompt = state["system_prompt"]
    search_enabled = state.get('search_enabled',False)
    
    
    base_model = get_model_instance(model_provider, model_name, temperature, max_tokens)
    if search_enabled:
        base_model = base_model.bind_tools([web_search])

    retrieved_context = state.get("current_context",None)
    if not retrieved_context:
        retrieved_context = state.get("messages",[{"content": "SYSTEM OBSERVATION: unable to fetch the context"}])[-1].content
    messages = [SystemMessage(content=f"""{system_prompt}

STRICT CONTEXT GROUNDING & RESPONSE RULES:
1. Grounding: Answer the query relying ONLY on the RETRIEVED CONTEXT provided below. Do NOT use unverified outside facts or assumptions.
2. Anti-Hallucination: If the answer is not present in or directly inferable from the context, respond strictly with:
   "I cannot find this information in the provided context."
3. Partial Information: If the context partially answers the query, answer what is directly supported and explicitly list the missing details.
4. Structure: Keep responses clear, professional, and well-structured using bullet points where applicable.

EXAMPLES:
- Context: "Employee annual leave is 20 days. Health insurance covers full dental."
  Query: "What is the leave policy?" -> "According to the provided context, annual leave for employees is 20 days."
  Query: "What is the 401k match?" -> "I cannot find this information in the provided context."

QUERY:
{state['query'][-1]}

RETRIEVED CONTEXT:
{retrieved_context}
"""), *state["messages"][-5:]]

    await asyncio.sleep(2.5)
    response = await base_model.ainvoke(messages)
    
    return {"messages": [response], "node_output": [response]}

@observable_node("generic_response_node")
async def generic_response_node(state: AgentState, config: RunnableConfig):
    '''
    a simple node that analyses the current conversation. If the query is generic
    or the question is repetitive, whose answer is already been fetched and exists in the conversation history, then it 
    routes to the end node directly without calling the LLM again
    '''
    
    system_prompt = SystemMessage(content="""You are a polite, history-grounded assistant.
- Answer casual greetings, pleasantries, or questions using ONLY conversation history.
- If a question requires document knowledge not in history, politely inform the user to ask a specific topic question.
- Keep responses brief, friendly, and direct.""")
    
    model_provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    
    llm_model = get_model_instance(model_provider, model_name, temperature, max_tokens)
    full_messages = [system_prompt] + state["messages"]
    await asyncio.sleep(2.5)
    response = await llm_model.ainvoke(full_messages)
    
    return {
        "messages": [response],
        "query_context_pairs": [{
            "query": state["query"][-1],
            "context_received": "",
            "context_found": True,
            "query_type": "generic_or_repetitive"
        }],
        "query_type": "generic_or_repetitive",
        "node_output": [response]
    }
    
@observable_node("evalator_node")   
async def response_evaluation_node(state:AgentState, config: RunnableConfig):
    max_iter = state.get("max_iter", 0)
    if max_iter >= 2:
        return {"route": ["unsatisfactory"], "node_output": [{"reason": "max_iter reached"}]}
    
    # Extract just the specific text the judge needs
    original_query = state["query"][0]
    latest_query = state["query"][-1]
    drafted_response = state["messages"][-1].content
    retrieved_context = state.get("current_context",None)
    if not retrieved_context:
        retrieved_context = state.get("messages",[{"content": "SYSTEM OBSERVATION: unable to fetch the context"}])[-1].content
    
    system_prompt = SystemMessage(
            content=f"""Evaluate if the Assistant Response adequately answers the Query using the Context.

Original Query: {original_query}
Current Query: {latest_query}
Context: {retrieved_context}
Assistant Response: {drafted_response}
Iteration: {state.get('max_iter', 0) + 1}

Output EXACTLY one option:
- satisfactory
- query_rephrase - [remark]
- revise - [remark]
- clarify - [remark]"""
        )
    
    provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    
    llm = get_model_instance(provider, model_name, temperature, max_tokens)
    
    # ONLY pass the system prompt. We don't need the whole chat history!
    full_messages = [system_prompt] 
    
    await asyncio.sleep(2.5)
    response = await llm.ainvoke(full_messages)

    if response.content.strip().lower() == "satisfactory":
        return {"route": ["satisfactory"], "max_iter": max_iter + 1, "node_output": [response]}
    elif response.content.strip().lower().startswith("query_rephrase"):
        return {"route": ["query_rephrase"], "max_iter": max_iter + 1, "remarks": response.content, "node_output": [response]}
    elif response.content.strip().lower().startswith("clarify"):
        return {"route": ["clarify"], "max_iter": max_iter + 1, "remarks": response.content, "node_output": [response]}
    else:
        return {"route": ["revise"], "max_iter": max_iter + 1, "remarks": response.content, "node_output": [response]}

@observable_node("query_rephraser_node")
async def query_rephraser_node(state:AgentState, config: RunnableConfig):
    """
    This node rephrases the user query if the response generated is not satisfactory. It takes the original query and the conversation history as input and rephrases the query in a way that it can be answered effectively by the LLM. The rephrased query is then sent back to the conditional router node 1 for re-evaluation.
    """
    
    query = state["query"][-1]
    remarks = state['remarks']
    system_prompt = SystemMessage(
            content=f"""You are an expert query rewriter for document retrieval.

INSTRUCTIONS:
1. Rewrite the user's latest query into a clear, specific, and self-contained question that preserves original intent.
2. Use conversation history ONLY to resolve ambiguous pronouns (e.g., "it", "they", "that policy") and missing references.
3. Do NOT answer the query, add unverified facts, or include explanations. Output ONLY the rewritten query string.

EXAMPLES:
- History: "Tell me about the remote work policy." -> User: "Does it apply to contractors?"
  Rewritten Query: "Does the remote work policy apply to contractors?"
- History: "What are the salary types?" -> User: "explain the second one"
  Rewritten Query: "Explain the second type of salary component listed in the document."

Judge Remarks: {remarks}
Latest Query: {query}"""
        )    
    provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    llm = get_model_instance(provider, model_name, temperature, max_tokens)
    
    full_messages = [system_prompt] + state["messages"]
    
    await asyncio.sleep(2.5)
    response = await llm.ainvoke(full_messages)
    
    return {"query": [response.content.strip()],"current_context": None, "messages": [HumanMessage(content=response.content.strip())], "node_output": [response]}

@observable_node("unsatisfactory_handle_node")
async def unsatisfactory_handler_node(state: AgentState, config: RunnableConfig):
    """
    This node returns the most recent valid AI response with a disclaimer when max iterations is reached.
    """
    last_ai_response = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content and isinstance(msg.content, str) and msg.content.strip():
            last_ai_response = msg.content.strip()
            break
            
    if not last_ai_response:
        last_ai_response = "I don't have enough context in the uploaded documents to answer your query accurately."

    disclaimer = "⚠️ Disclaimer: Maximum processing iterations reached. The response below may be incomplete:\n\n"
    response = AIMessage(content=disclaimer + last_ai_response)
    return {"disclaimer": True, "messages": [response], "node_output": [response]}

@observable_node("clarify_node")
async def clarify_node(state: AgentState, config: RunnableConfig):
    """
    This node asks the user for clarification if the query is too ambiguous to answer or retrieve context for.
    """
    query = state["query"][-1] if state.get("query") else ""
    remarks = state.get('remarks', 'The query is too vague.')
    system_prompt = SystemMessage(
            content=f"""Draft a polite, concise 1-sentence request asking the user to clarify their vague query.

Query: {query}
Remarks: {remarks}

Output ONLY the clarification request."""
        )    
    provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    llm = get_model_instance(provider, model_name, temperature, max_tokens)
    
    full_messages = [system_prompt]
    
    await asyncio.sleep(2.5)
    response = await llm.ainvoke(full_messages)
    
    if not response.content or not isinstance(response.content, str) or not response.content.strip():
        response = AIMessage(content="Could you please provide more details or clarify your query?")
        
    return {"messages": [response], "node_output": [response]}


@observable_node("start_node")
async def start_node(state: AgentState, config: RunnableConfig):
    # Pass-through node to log the start state in trajectory
    return {}


@observable_node("start_node")
def start_node(state: AgentState, config: RunnableConfig):
    query = state["query"][-1]
    msgs = state.get("messages", [])
    if not msgs or not any(isinstance(m, HumanMessage) and m.content == query for m in msgs):
        return {"messages": [HumanMessage(content=query)]}
    return {}

def return_response(state: AgentState, config: RunnableConfig) -> str:
    return state["route"][-1]



def get_chatbot_agent():
    """
    Singleton provider. Returns the compiled graph instance.
    If it doesn't exist yet, it compiles it once and caches it in RAM.
    """
    global _compiled_graph_instance
    
    if _compiled_graph_instance is None:
        print("Initializing and Compiling LangGraph Chatbot Engine...")
        
        graph_builder = StateGraph(AgentState)
        graph_builder.add_node("start_node", start_node)
        graph_builder.add_node("genuine_generic_router", conditional_router_node_1)
        graph_builder.add_node("context_retriver", retrieve_context)
        graph_builder.add_node("query_rephraser_node", query_rephraser_node)
        graph_builder.add_node("chatbot_node", chatbot_node)
        graph_builder.add_node("generic_response_node", generic_response_node)
        graph_builder.add_node("evalator_node", response_evaluation_node)
        graph_builder.add_node("unsatisfactory_handle_node", unsatisfactory_handler_node)
        graph_builder.add_node("clarify_node", clarify_node)
        graph_builder.add_node("tools",ToolNode(tools=[web_search]))
        
        
        graph_builder.add_edge(START, "start_node")
        graph_builder.add_edge("start_node", "genuine_generic_router")
        graph_builder.add_conditional_edges("genuine_generic_router", return_response,
                                           {
                                               "generic_or_repetitive": "generic_response_node",
                                               "genuine_query": "context_retriver"
                                           })
        graph_builder.add_edge("context_retriver","chatbot_node")
        graph_builder.add_edge("generic_response_node", END)
        graph_builder.add_conditional_edges("chatbot_node", route_after_chatbot,{
                                                    "tools": "tools",
                                                    "response_evaluation_node": "evalator_node"
                                                }
        )
        graph_builder.add_edge("tools", "chatbot_node")
        graph_builder.add_conditional_edges("evalator_node", return_response,{
                                                  "satisfactory": END,
                                                  "unsatisfactory":  "unsatisfactory_handle_node",
                                                  "query_rephrase": "query_rephraser_node",
                                                  "revise":"chatbot_node",
                                                  "clarify": "clarify_node"
                                             })
        graph_builder.add_edge("query_rephraser_node", "context_retriver")
        graph_builder.add_edge("unsatisfactory_handle_node", END)        
        graph_builder.add_edge("clarify_node", END) 
        _compiled_graph_instance = graph_builder.compile()       
        
    return _compiled_graph_instance



