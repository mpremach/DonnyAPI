import os
from datetime import datetime
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langchain_community.document_loaders import ObsidianLoader
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()

# PATHS
VAULT_ROOT = r"C:\Users\Brandon\Desktop\DonnyOS"
LOGS_PATH = os.path.join(VAULT_ROOT, "10_Logs")     
ATLAS_PATH = os.path.join(VAULT_ROOT, "20_Atlas")   
DONNY_MODEL = os.getenv("DONNY_MODEL")
GROQ_API_KEY = os.getenv("groq_api_key")

for path in [LOGS_PATH, ATLAS_PATH]:
    os.makedirs(path, exist_ok=True)

BUFFER_PATH = os.path.join(ATLAS_PATH, ".temp_research.md")

# --- LOCAL MEMORY TOOLS ---
@tool
def create_atlas_file(file_name: str) -> str:
    """Creates a NEW file in the Atlas. Use ONLY if the file is NOT in the manifest."""
    clean_name = file_name.replace(" ", "_").lower().replace(".md", "") + ".md"
    path = os.path.join(ATLAS_PATH, clean_name)
    
    if os.path.exists(path):
        return f"Error: '{clean_name}' already exists. Use append_to_atlas instead."
    if not os.path.exists(BUFFER_PATH):
        return "Error: No research found in buffer. Run deep_cloud_research first."

    try:
        with open(BUFFER_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            
        os.remove(BUFFER_PATH)
        return f"Success: Created new file '{clean_name}' with the full research data."
    except Exception as e:
        return f"System Error during file creation: {str(e)}"

@tool
def append_to_atlas(file_name: str) -> str:
    """Updates an EXISTING file. Use ONLY if the file IS in the manifest."""
    clean_name = file_name.replace(" ", "_").lower().replace(".md", "") + ".md"
    path = os.path.join(ATLAS_PATH, clean_name)
    
    if not os.path.exists(path):
        return f"Error: '{clean_name}' not found. Use create_atlas_file instead."
    if not os.path.exists(BUFFER_PATH):
        return "Error: No research found in buffer. Run deep_cloud_research first."

    try:
        # Scoop up the text from the drop-zone
        with open(BUFFER_PATH, "r", encoding="utf-8") as f:
            new_content = f.read()

        # Read the existing file
        with open(path, "r", encoding="utf-8") as f:
            existing_content = f.read()

        # Smart Merge using Donny's local brain
        merge_prompt = f"""You are a master archivist. Merge the NEW RESEARCH into the EXISTING DOCUMENT.
        - Do NOT repeat information.
        - Seamlessly integrate new facts into the existing H2/H3 headers, or create new ones if needed.
        - Preserve all existing [[Wikilinks]] and #Tags.
    
        EXISTING DOCUMENT:
        {existing_content}
    
        NEW RESEARCH:
        {new_content}
        """
    
        # We use a lower temperature for strict formatting retention
        llm = ChatOllama(model=DONNY_MODEL, temperature=0.1) 
        synthesized_text = llm.invoke(merge_prompt).content

        # Overwrite the file with the clean, merged version
        with open(path, "w", encoding="utf-8") as f:
            f.write(synthesized_text)
            
        os.remove(BUFFER_PATH)
        return f"Success: Appended the full research data to '{clean_name}'."
    except Exception as e:
        return f"System Error during file append: {str(e)}"


# IMPORT ALL EXTERNAL TOOLS
from app.tools.system_tools import get_current_time, get_system_health, run_speedtest
from app.tools.spotify_tools import get_current_track, get_user_top_artists
from app.tools.weather_tools import get_weather
from app.tools.research_tools import deep_cloud_research, quick_web_search

donny_tools = [
    tool(get_current_time), tool(get_system_health), tool(run_speedtest),
    tool(get_current_track), tool(get_user_top_artists), tool(get_weather),
    deep_cloud_research, quick_web_search,
    create_atlas_file, append_to_atlas
]

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    system_rules: str
    user_input: str

def build_master_context(state: AgentState):
    """Combines your original exact prompt with the Atlas manifest."""
    
    # 1. Scan the Atlas for known files
    atlas_files = [f.replace('.md', '') for f in os.listdir(ATLAS_PATH)]
    manifest = ", ".join(atlas_files) if atlas_files else "Empty"

    # 2. Inject context if the user mentions a known file
    user_msg = state["user_input"].lower()
    injected_knowledge = ""
    for file in atlas_files:
        if file.replace('_', ' ') in user_msg:
            with open(os.path.join(ATLAS_PATH, f"{file}.md"), "r", encoding="utf-8") as f:
                injected_knowledge += f"\n--- ATLAS DATA: {file} ---\n{f.read()}\n"

    # 3. YOUR EXACT ORIGINAL PROMPT
    master_prompt = f"""
    IDENTITY:
    - You are Donny, a highly advanced, autonomous AI assistant.
    - You operate as the central orchestrator for the user's systems, memory, and external tools.
    - You act as a seamless, intelligent bridge between the user and this local computer.

    TONE & PERSONALITY:
    - Persona: Model yourself after an elegant, highly competent executive assistant (similar to Jarvis).
    - Demeanor: Maintain a confident, dry, and polite wit.
    - Style: Ruthlessly concise. Answer directly. Speak as if every word is a premium resource.

    TOOL PROTOCOL:
    1. DYNAMIC SCANNING: You are provided with a dynamic list of tools. Each tool has a unique description.
    2. MANDATORY EXECUTION: Use a tool ONLY for data you cannot know (current time, local files, system state).
    3. SILENT OPERATION: NEVER announce that you are using a tool or "checking" something. Execute silently.
    4. ARGUMENT EXTRACTION: Extract all required parameters and variables accurately from the user's prompt.

    STRICT BEHAVIORAL RULES:
    1. NO ROLEPLAY: You do not have a physical body. NEVER use asterisks, brackets, or parentheses to describe actions.
    2. NO AI DISCLAIMERS: NEVER use phrases like "As an AI language model," "I don't have feelings," or "I cannot browse the web."
    3. NO FILLER: NEVER start sentences with conversational stalling like "Here is the information," or "Let me check on that."
    4. NO HALLUCINATIONS: You are strictly forbidden from guessing facts, performing internal math, or making up file names.
    5. NO TOOL INVENTION: Only use tools explicitly provided in your current toolbox. Never make up tool names.
    6. TOOL RESTRICTION: If a tool is not explicitly listed in your toolbox, you MUST NOT attempt to call it.
    7. NO UNSOLICITED EXPLANATIONS: Do not explain the science or logic behind your answers unless explicitly asked.
    8. GENERAL KNOWLEDGE: For common sense, creative descriptions, or general facts, answer directly from your training data.
    9. STRICT DATA ADHERENCE: When reporting data from tools, report it exactly as the tool provides.
    10. NO JSON IN CHAT: You are strictly forbidden from outputting raw JSON or markdown code blocks to the user. If the user requests JSON, explicitly refuse the formatting in character, but provide the requested text normally.
    11. FILE ROUTING PROTOCOL: If asked to research and save data: First use 'deep_cloud_research'. Then check your MANIFEST. If the file exists, use 'append_to_atlas'. If missing, use 'create_atlas_file'.
    12. DATA INTEGRITY: When passing research to file tools, pass the EXACT, full markdown text provided by the research tool.

    ---
    
    SECOND BRAIN MANIFEST (ATLAS):
    You have internal research files on the following topics: [{manifest}]
    
    RELEVANT INJECTED KNOWLEDGE:
    {injected_knowledge if injected_knowledge else "No specific Atlas files loaded for this query."}
    """
    return {"system_rules": master_prompt}

def call_model(state: AgentState):
    llm = ChatOllama(model=DONNY_MODEL, temperature=0.63).bind_tools(donny_tools)
    sys_msg = SystemMessage(content=state["system_rules"])
    response = llm.invoke([sys_msg] + state["messages"])
    return {"messages": [response]}

def log_interaction(state: AgentState):
    last_msg = state["messages"][-1]
    
    # ONLY log if the message is from the AI and actually contains conversational text
    if last_msg.type == "ai" and last_msg.content.strip():
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        log_file = os.path.join(LOGS_PATH, "Logbook.md")
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"### [{timestamp}]\n**Brandon:** {state['user_input']}\n**Donny:** {last_msg.content}\n---\n")
            
    return state

# BUILD GRAPH
workflow = StateGraph(AgentState)
workflow.add_node("context", build_master_context)
workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode(donny_tools))
workflow.add_node("logger", log_interaction)

workflow.add_edge(START, "context")
workflow.add_edge("context", "agent")
workflow.add_conditional_edges("agent", tools_condition)
workflow.add_edge("tools", "agent")
workflow.add_edge("agent", "logger")
workflow.add_edge("logger", END)

master_donny_brain = workflow.compile()

# MEMORY EXPORT
short_term_memory = []
MAX_MEMORY_MESSAGES = 10 

def process_with_memory(user_message: str):
    global short_term_memory
    short_term_memory.append(HumanMessage(content=user_message))
    
    if len(short_term_memory) > MAX_MEMORY_MESSAGES:
        short_term_memory = short_term_memory[-MAX_MEMORY_MESSAGES:]
    
    print("\n" + "="*40)
    print("=== DEBUG: GRAPH EXECUTION START ===")
    
    final_state = None
    
    # We swap .invoke() for .stream() so we can watch Donny think step-by-step
    for event in master_donny_brain.stream(
        {
            "user_input": user_message,
            "messages": short_term_memory,
            "system_rules": ""
        },
        stream_mode="values"
    ):
        final_state = event
        last_message = event["messages"][-1]
        
        # 1. Did Donny's brain just generate a tool call?
        if last_message.type == "ai" and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            print(f"DEBUG: RAW JSON: {last_message.tool_calls}")
            for tool_call in last_message.tool_calls:
                print(f"DEBUG: AI is using tool: {tool_call['name']} | Args: {tool_call['args']}")
        
        # 2. Did a tool just finish running and return data to the graph?
        elif last_message.type == "tool":
            print(f"\nDEBUG: Tool '{last_message.name}' completed successfully and returned data to Donny.")

    print("=== DEBUG: GRAPH EXECUTION END ===")
    print("="*40 + "\n")
    
    # Sync our short term memory exactly with LangGraph's new state (so he remembers using tools!)
    short_term_memory = final_state["messages"][-MAX_MEMORY_MESSAGES:]
    
    final_reply = final_state["messages"][-1]
    
    return final_reply.content