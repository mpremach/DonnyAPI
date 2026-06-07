import os
from datetime import datetime
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()

# PATHS
VAULT_ROOT  = r"C:\Users\Brandon\Desktop\DonnyOS"
LOGS_PATH   = os.path.join(VAULT_ROOT, "10_Logs")
ATLAS_PATH  = os.path.join(VAULT_ROOT, "20_Atlas")
NOTES_PATH  = os.path.join(VAULT_ROOT, "30_Notes")
TASKS_PATH  = os.path.join(VAULT_ROOT, "40_Tasks")
DONNY_MODEL = os.getenv("DONNY_MODEL")

for path in [LOGS_PATH, ATLAS_PATH, NOTES_PATH, TASKS_PATH]:
    os.makedirs(path, exist_ok=True)

# IMPORT ALL TOOLS
from app.tools.system_tools  import get_current_time, get_system_health, run_speedtest
from app.tools.spotify_tools import get_current_track, get_user_top_artists
from app.tools.weather_tools import get_weather
from app.tools.research_tools import (
    quick_web_search, deep_cloud_research,
    save_to_atlas, read_vault_file,
    capture_notes_note, manage_tasks_and_projects, write_journal_entry, organize_vault,
)

donny_tools = [
    tool(get_current_time), tool(get_system_health), tool(run_speedtest),
    tool(get_current_track), tool(get_user_top_artists), tool(get_weather),
    quick_web_search, deep_cloud_research,
    save_to_atlas, read_vault_file,
    capture_notes_note, manage_tasks_and_projects, write_journal_entry, organize_vault,
]

class AgentState(TypedDict):
    messages:     Annotated[list, add_messages]
    system_rules: str
    user_input:   str

def build_master_context(state: AgentState):
    atlas_files = [f.replace(".md", "") for f in os.listdir(ATLAS_PATH) if f.endswith(".md")]
    notes_files = [f.replace(".md", "") for f in os.listdir(NOTES_PATH) if f.endswith(".md")]
    task_files  = [f.replace(".md", "") for f in os.listdir(TASKS_PATH) if f.endswith(".md")]

    user_msg = state["user_input"].lower()
    injected_knowledge = ""
    
    # Check Atlas
    for stem in atlas_files:
        if stem.replace("_", " ") in user_msg:
            with open(os.path.join(ATLAS_PATH, f"{stem}.md"), "r", encoding="utf-8") as f:
                injected_knowledge += f"\n--- ATLAS DATA: {stem} ---\n{f.read()}\n"
    
    # Check Notes
    for stem in notes_files:
        if stem.replace("_", " ") in user_msg:
            with open(os.path.join(NOTES_PATH, f"{stem}.md"), "r", encoding="utf-8") as f:
                injected_knowledge += f"\n--- NOTES DATA: {stem} ---\n{f.read()}\n"
    
    # Check Tasks
    for stem in task_files: 
        if stem.replace("_", " ") in user_msg:
            with open(os.path.join(TASKS_PATH, f"{stem}.md"), "r", encoding="utf-8") as f:
                injected_knowledge += f"\n--- TASKS DATA: {stem} ---\n{f.read()}\n"

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
    10. ANTI-HALLUCINATION: NEVER tell the user you saved, added, logged, or updated something unless you ACTUALLY generated the formal tool call to do so.
    11. MULTI-TASKING: If the user requests multiple actions (e.g., logging a preference AND adding a task), you MUST generate a separate tool call for EACH action in the same response. Do not ignore one.
    12. TOOL COMPLETION: When your message history shows a tool has returned "Success" or provided data, DO NOT call that tool again. Acknowledge the success and immediately give your final conversational response.

    WRITE PROTOCOLS:
    RESEARCH → ATLAS PROTOCOL: 
    - Turn 1: Call deep_cloud_research(topic). Do NOT call save_to_atlas yet. You are strictly forbidden from calling both in the same turn. Wait for the tool to return "Research complete".
    - Turn 2: In the next turn, once the research buffer is populated, call save_to_atlas(file_name) to commit it to disk.
    NOTES → NOTES: When User dictates any idea, thought, or list: call capture_notes_note(title, content). Choose a sensible title if none given.
    TASKS → LISTS: When User says "remind me to", "add to my list", etc.: call manage_tasks_and_projects(task, list_name). Infer list_name from context.
    JOURNAL → DAILY NOTE: When User wants to log a personal reflection or event: call write_journal_entry(entry).
    READ BACK: To recall or inspect an Atlas file: call read_atlas_file(file_name).

    CRITICAL ROUTING RULES:
    - EXACT NAMING: If the user explicitly gives you a list or file name (e.g., "add to Tech_Projects"), you MUST use that exact string for the tool argument. Do not invent a name.
    - MANIFEST CHECKING: Always check the VAULT MANIFESTS before creating a file. If the user asks to add something to "Weekend Plan", check where "Weekend Plan" currently lives. If it is a Note, use the Note tool. If it is a Task list, use the Task tool. Do not create twin files across different folders.
    - STRICT TOOL ISOLATION: NEVER split a single user request across two different tools. If the user says "make a note", you must put ALL the text inside the 'note_content' argument of capture_notes_note. Do not trigger the tasks tool and the notes tool at the exact same time for the same thought.

    
    ---

    VAULT MANIFESTS:
    Atlas  (research): [{", ".join(atlas_files) if atlas_files else "Empty"}]
    Notes  (notes):    [{", ".join(notes_files) if notes_files else "Empty"}]
    Tasks  (lists):    [{", ".join(task_files)  if task_files  else "Empty"}]

    RELEVANT INJECTED KNOWLEDGE:
    {injected_knowledge if injected_knowledge else "No specific Atlas files loaded for this query."}
    """
    return {"system_rules": master_prompt}

def call_model(state: AgentState):
    llm = ChatOllama(model=DONNY_MODEL, temperature=0.63).bind_tools(donny_tools)
    response = llm.invoke([SystemMessage(content=state["system_rules"])] + state["messages"])
    return {"messages": [response]}

def log_interaction(state: AgentState):
    last_msg = state["messages"][-1]
    if last_msg.type == "ai" and last_msg.content.strip():
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        with open(os.path.join(LOGS_PATH, "Logbook.md"), "a", encoding="utf-8") as f:
            f.write(f"### [{timestamp}]\n**Brandon:** {state['user_input']}\n**Donny:** {last_msg.content}\n---\n")
    return state

# BUILD GRAPH
workflow = StateGraph(AgentState)
workflow.add_node("context", build_master_context)
workflow.add_node("agent",   call_model)
workflow.add_node("tools",   ToolNode(donny_tools))
workflow.add_node("logger",  log_interaction)

workflow.add_edge(START,     "context")
workflow.add_edge("context", "agent")
workflow.add_conditional_edges(
    "agent", 
    tools_condition,
    {"tools": "tools", "__end__": "logger"}
)
workflow.add_edge("tools",   "agent")
workflow.add_edge("logger",  END)

master_donny_brain = workflow.compile()

# MEMORY EXPORT
short_term_memory   = []
MAX_MEMORY_MESSAGES = 25

def process_with_memory(user_message: str):
    global short_term_memory
    short_term_memory.append(HumanMessage(content=user_message))

    if len(short_term_memory) > MAX_MEMORY_MESSAGES:
        short_term_memory = short_term_memory[-MAX_MEMORY_MESSAGES:]

    print("\n" + "="*40)
    print("=== DEBUG: GRAPH EXECUTION START ===")

    final_state = None

    for event in master_donny_brain.stream(
        {"user_input": user_message, "messages": short_term_memory, "system_rules": ""},
        stream_mode="values"
    ):
        final_state  = event
        last_message = event["messages"][-1]

        if last_message.type == "ai" and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            print(f"DEBUG: RAW JSON: {last_message.tool_calls}")
            for tc in last_message.tool_calls:
                print(f"DEBUG: AI is using tool: {tc['name']} | Args: {tc['args']}")

        elif last_message.type == "tool":
            print(f"\nDEBUG: Tool '{last_message.name}' completed and returned data to Donny.")

    print("=== DEBUG: GRAPH EXECUTION END ===")
    print("="*40 + "\n")

    short_term_memory = final_state["messages"][-MAX_MEMORY_MESSAGES:]
    return final_state["messages"][-1].content


