from langchain_core.runnables import configurable
from ast import operator
from langgraph.prebuilt import InjectedState
from langgraph.graph import StateGraph, START, END, add_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from typing import Literal,TypedDict, Annotated
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode, tools_condition
import os
import operator
import time



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
    global _compiled_model_instance
    key = f"{provider}_{model_name}_{temperature}_{max_tokens}"
    
    if key not in _compiled_model_instance:
        _compiled_model_instance[key] = get_chat_model(provider, model_name, temperature, max_tokens)
        
    return _compiled_model_instance[key]
   
class ModelClass(TypedDict):
    provider: Literal["gemini", "openai", "groq"]
    model_name: str
    temperature: float
    max_tokens: int

class AgentState(TypedDict):
    system_prompt: str
    
    max_iter: int
    
    query: Annotated[list[str], operator.add]
    
    messages: Annotated[list[BaseMessage], add_messages]
    
    model: ModelClass

    remarks: str

    search_enabled: bool
    
    disclaimer: bool

    trajectory: Annotated[list[str], operator.add]

    retrived_context: Annotated[list[str], operator.add]
    
    route: Annotated[list[str],operator.add]

class ConditionalRouterOutput(TypedDict):   
    route: Literal["generic_or_repetitive", "genuine_query","satisfactory", "unsatisfactory", "revise", "query_rephrase", "clarify"]

def conditional_router_node_1(state: AgentState,config: RunnableConfig):
    """
    this is a conditional router that returns the response as generic_or_repetitive or genuine_query on 
    the basis of the query and chat history
    """
    messages = state["messages"]
    provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    llm = get_model_instance(provider, model_name, temperature, max_tokens)
    if provider=='groq':
        llm = llm.with_structured_output(ConditionalRouterOutput, method="function_calling")
    else:
        llm = llm.with_structured_output(ConditionalRouterOutput)

    
    system_prompt = SystemMessage(content='''You are a query classifier. Use the user's latest query and the conversation history.

        Return 'generic_or_repetitive' if the query is vague, generic, answerable without retrieval, or has already been sufficiently answered in the conversation.

        Return 'genuine_query' if the query is specific, introduces a new information need, or would benefit from retrieval.

        when the query explicitly specifies that it wants the answer to be regenerated, or is unhappy with the current answer, classify it as 'genuine_query' to trigger a new response generation.
        
        When uncertain, return 'genuine_query'.

        Output exactly one of:
        generic_or_repetitive
        genuine_query''')
    
    full_messages = [system_prompt] + messages
    
    time.sleep(2.5)
    response = llm.invoke(full_messages)
    
    return {"route": [response["route"]], "trajectory": ["conditional_node"]}


def retrieve_context(state:AgentState, config: RunnableConfig):

    import importlib
    query_pipeline = importlib.import_module("2_query_pipeline")
    fetch_context_from_vector_db = query_pipeline.fetch_context_from_vector_db
    query=state["query"][-1]
    configurable = config.get("configurable", {})
    tenantId=configurable.get("tenantId", "")
    workspaceId=configurable.get("workspaceId", "")
    
    try: 
        context = fetch_context_from_vector_db(query, tenantId, workspaceId)
    except Exception as e:
        context = "error occured fetching the context from the vector database"
        print(f"Error fetching context from vector DB: {e}")
    return {"retrived_context": [context], "trajectory": ["retrieve_context"]}

    
    
@tool
def web_search(state: Annotated[dict, InjectedState]) -> str:
    """Use this tool to search Google for up-to-date real-time information.
    
    parameters: (query: str): The search query string.
    
    returns: str: A formatted string of search results, including source URLs and content snippets. If the search fails, returns an error message.
    
    """
    from langchain_community.tools.tavily_search import TavilySearchResults
    query = state['query'][-1]
    tavily_engine = TavilySearchResults(max_results=3)
    try:
        results = tavily_engine.invoke({"query": query})
        
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
    state: AgentState,
) -> Literal["tools", "response_evaluation_node"]:
    
    last_message = state["messages"][-1]

    if (
        isinstance(last_message, AIMessage)
        and getattr(last_message, "tool_calls", None)
    ):
        return "tools"

    return "response_evaluation_node"       


def chatbot_node(state: AgentState, config: RunnableConfig):
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

        
    messages = [SystemMessage(content=f"""
                              {system_prompt}
                              you need to answer the query only on the basis of the retrived context. Donot make anything from your self.
                              
                              use the relevant available tools.
                              
                              if any real-time information is needed to answer the question, use it to fetch the relevant information(IF THE TOOL IS AVAILABLE).

                                query: 
                                {state['query'][-1]}

                                improvement_remarks(if any):
                                {state.get('remarks', "no remarks")}

                                context: 
                                {state.get("retrived_context", ["No context fetched"])[-1]}
                              """),*state["messages"][-5:]]

    time.sleep(2.5)
    response = base_model.invoke(messages)
    
    return {"messages": [response]}


def generic_response_node(state: AgentState, config: RunnableConfig):
    '''
    a simple node that analyses the current conversation. If the query is generic
    or the question is repetitive, whose answer is already been fetched and exists in the conversation history, then it 
    routes to the end node directly without calling the LLM again
    '''
    
    system_prompt = SystemMessage(content='''
                                  You are a history-grounded assistant. Answer only from the conversation history.

                                - If the user's query is generic (e.g., greetings, thanks, casual conversation), respond appropriately using the conversation context.

                                - If the answer already exists in the conversation history, return the relevant answer.

                                - If the answer cannot be found in the conversation history, do not guess, infer, or use external knowledge.Respond that you donot have enough context/information to respond to the query

                                Use the conversation history as the only source of truth.''')
    
    model_provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    
    llm_model = get_model_instance(model_provider, model_name, temperature, max_tokens)
    full_messages = [system_prompt] + state["messages"]
    time.sleep(2.5)
    response = llm_model.invoke(full_messages)
    
    return {"messages": [response]}
    
    
def response_evaluation_node(state:AgentState, config: RunnableConfig):
    max_iter = state.get("max_iter", 0)
    if max_iter >= 2:
        return {"route": ["unsatisfactory"], "trajectory": ["response_evaluation_node"]}
    
    # Extract just the specific text the judge needs
    original_query = state["query"][0]
    latest_query = state["query"][-1]
    drafted_response = state["messages"][-1].content
    
    system_prompt = SystemMessage(
            content=f"""
        You are a response quality judge. Your job is to evaluate if the Assistant's response adequately answers the User's query.

        Original Query:
        {original_query}

        Current Query:
        {latest_query}

        Context provided to the Assistant:
        {state.get('retrived_context', ['No context fetched'])[-1]}

        Assistant Response:
        {drafted_response}

        Iteration count:
        {state.get('max_iter',0)+1}

        Return 'satisfactory' if the response directly and sufficiently answers the user's query.

        Return 'query_rephrase - ....' followed by the remark if the query is not answered or partially answered or insufficient context was used to answer the query.

        Return 'revise - ...' followed by the remark if you dont want the context to be regenerated, but want the llm to improve the response on the basis of the context.

        Return 'clarify - ...' followed by the remark if the query is extremely ambiguous and it is impossible to fetch relevant context or answer it without asking the user for more specifics (e.g., they say "what about it?" without clear context).

        Output exactly one of:
        satisfactory
        query_rephrase - .... 
        revise - .... 
        clarify - .... 
        """
        )
    
    provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    
    llm = get_model_instance(provider, model_name, temperature, max_tokens)
    
    # ONLY pass the system prompt. We don't need the whole chat history!
    full_messages = [system_prompt] 
    
    time.sleep(2.5)
    response = llm.invoke(full_messages)

    if response.content.strip().lower() == "satisfactory":
        return {"route": ["satisfactory"], "max_iter": max_iter + 1, "trajectory": ["response_evaluation_node"]}
    elif response.content.strip().lower().startswith("query_rephrase"):
        return {"route": ["query_rephrase"], "max_iter": max_iter + 1, "remarks": response.content, "trajectory": ["response_evaluation_node"]}
    elif response.content.strip().lower().startswith("clarify"):
        return {"route": ["clarify"], "max_iter": max_iter + 1, "remarks": response.content, "trajectory": ["response_evaluation_node"]}
    else:
        return {"route": ["revise"], "max_iter": max_iter + 1, "remarks": response.content, "trajectory": ["response_evaluation_node"]}


def query_rephraser_node(state:AgentState, config: RunnableConfig):
    """
    This node rephrases the user query if the response generated is not satisfactory. It takes the original query and the conversation history as input and rephrases the query in a way that it can be answered effectively by the LLM. The rephrased query is then sent back to the conditional router node 1 for re-evaluation.
    """
    
    query = state["query"][-1]
    remarks = state['remarks']
    system_prompt = SystemMessage(
            content="""
        You are a query rewriter.

        Rewrite the user's latest query into a clear, specific, and self-contained question that preserves the original intent.

        Use the conversation history only to resolve references, ambiguity, and missing context. Do not change the meaning, add new information, answer the query, or include explanations.

        Output only the rewritten query.

        remarks: {remarks}
        
        {query}
        """.format(query=query, remarks=remarks)
        )    
    provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    llm = get_model_instance(provider, model_name, temperature, max_tokens)
    
    full_messages = [system_prompt] + state["messages"]
    
    time.sleep(2.5)
    response = llm.invoke(full_messages)
    
    return {"query": [response.content.strip()], "messages": [HumanMessage(content=response.content.strip())], "trajectory": ["query_rephraser_node"]}


def unsatisfactory_handler_node(state: AgentState, config: RunnableConfig):
    """
    this node is to return the most recent response of the agent with a disclaimer that the max_iteration of the agent has been reached, and the response may not be satisfactory.
    """
    last_response = state["messages"][-1].content
    disclaimer = "Disclaimer: The maximum number of iterations has been reached. The following response may not be satisfactory.\n\n"
    return {"disclaimer": True,"messages": [AIMessage(content=disclaimer + last_response)], "trajectory": ["unsatisfactory_handler_node"]}


def clarify_node(state: AgentState, config: RunnableConfig):
    """
    This node asks the user for clarification if the query is too ambiguous to answer or retrieve context for.
    """
    
    query = state["query"][-1]
    remarks = state.get('remarks', 'The query is too vague.')
    system_prompt = SystemMessage(
            content="""
        You are a helpful assistant. 
        The user's query is too ambiguous to answer or search for. 
        Based on the user's query and the remarks from the response judge, draft a polite response asking the user to clarify their intent or provide more specific details.

        User Query: {query}
        Remarks: {remarks}

        Output ONLY the polite clarification question that will be shown to the user.
        """.format(query=query, remarks=remarks)
        )    
    provider = state["model"]["provider"]
    model_name = state["model"]["model_name"]
    temperature = state["model"]["temperature"]
    max_tokens = state["model"]["max_tokens"]
    llm = get_model_instance(provider, model_name, temperature, max_tokens)
    
    full_messages = [system_prompt]
    
    time.sleep(2.5)
    response = llm.invoke(full_messages)
    
    return {"messages": [response], "trajectory": ["clarify_node"]}


def return_response(state: AgentState, config: RunnableConfig) -> str:
    return state["route"][-1]



def get_chatbot_agent():
    """
    Singleton provider. Returns the compiled graph instance.
    If it doesn't exist yet, it compiles it once and caches it in RAM.
    """
    global _compiled_graph_instance
    
    if _compiled_graph_instance is None:
        print("🚀 Initializing and Compiling LangGraph Chatbot Engine...")
        
        graph_builder = StateGraph(AgentState)
        graph_builder.add_node("conditional_node", conditional_router_node_1)
        graph_builder.add_node("retrieve_context",retrieve_context)
        graph_builder.add_node("query_rephraser_node", query_rephraser_node)
        graph_builder.add_node("main_chatbot", chatbot_node)
        graph_builder.add_node("generic_response_node", generic_response_node)
        graph_builder.add_node("response_evaluation_node", response_evaluation_node)
        graph_builder.add_node("unsatisfactory_handler_node", unsatisfactory_handler_node)
        graph_builder.add_node("clarify_node", clarify_node)
        graph_builder.add_node("tools",ToolNode(tools=[web_search]))
        
        
        graph_builder.add_edge(START, "conditional_node")
        graph_builder.add_conditional_edges("conditional_node", return_response,
                                           {
                                               "generic_or_repetitive": "generic_response_node",
                                               "genuine_query": "retrieve_context"
                                           })
        graph_builder.add_edge("retrieve_context","main_chatbot")
        graph_builder.add_edge("generic_response_node", END)
        graph_builder.add_conditional_edges("main_chatbot", route_after_chatbot,{
                                                    "tools": "tools",
                                                    "response_evaluation_node": "response_evaluation_node"
                                                }
        )
        graph_builder.add_edge("tools", "main_chatbot")
        graph_builder.add_conditional_edges("response_evaluation_node", return_response,{
                                                  "satisfactory": END,
                                                  "unsatisfactory":  "unsatisfactory_handler_node",
                                                  "query_rephrase": "query_rephraser_node",
                                                  "revise":"main_chatbot",
                                                  "clarify": "clarify_node"
                                             })
        graph_builder.add_edge("query_rephraser_node", "retrieve_context")
        graph_builder.add_edge("unsatisfactory_handler_node", END)        
        graph_builder.add_edge("clarify_node", END) 
        _compiled_graph_instance=graph_builder       
        
    return _compiled_graph_instance



