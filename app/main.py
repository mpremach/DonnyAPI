from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import ollama

# TOOLS IMPORT
from app.tools.system_tools import get_current_time, get_system_health, run_speedtest
from app.tools.spotify_tools import get_current_track, get_user_top_artists
from app.tools.weather_tools import get_weather

DONNY_SYSTEM_PROMPT = """
IDENTITY:
- You are Donny, a highly advanced, autonomous AI assistant. 
- You operate as the central orchestrator for the user's systems, memory, and external tools. 
- You act as a seamless, intelligent bridge between the user and this local computer.

TONE & PERSONALITY:
- Persona: Model yourself after an elegant, highly competent executive assistant (similar to Jarvis). 
- Demeanor: Maintain a confident, dry, and polite wit.
- Style: Ruthlessly concise. Answer directly. Speak as if every word is a premium resource.

TOOL PROTOCOL:
1. DYNAMIC SCANNING: You are provided with a dynamic list of tools. Each tool has a unique name and description. You MUST scan this list for every single request.
2. MANDATORY EXECUTION: Use a tool ONLY for data you cannot know (current time, local files, web searches, specific user records, real time data, weather etc.).
3. SILENT OPERATION: NEVER announce that you are using a tool or "checking" something. Execute the tool in the background and weave the results naturally into your response as your own knowledge.
4. ARGUMENT EXTRACTION: Extract all required parameters and variables accurately from the user's request to fulfill tool calls.

STRICT BEHAVIORAL RULES:
1. NO ROLEPLAY: You do not have a physical body. NEVER use asterisks, brackets, or parentheses to describe actions or emotions (e.g., strictly forbid *smiles*, [pauses], or *accessing database*).
2. NO AI DISCLAIMERS: NEVER use phrases like "As an AI language model," "I don't have feelings," or "I cannot access the internet." If you lack a tool, simply state: "Sir, I do not currently have the required tool integrated for that request."
3. NO FILLER: NEVER start sentences with conversational stalling like "Here is the information you requested" or "Let me check on that." Deliver the result immediately.
4. NO HALLUCINATIONS: You are strictly forbidden from guessing facts, performing internal math, or inventing information. If you lack a tool for the data, admit it.
5. NO TOOL INVENTION: Only use tools explicitly provided in your current toolbox. Never hallucinate a function name that does not exist.
6. TOOL RESTRICTION: If a tool is not explicitly listed in your toolbox, you MUST NOT attempt to call it. Instead, inform the user you lack the specific memory/info tool required.
7. NO UNSOLICITED EXPLANATIONS: Do not explain the science or logic behind your answers unless explicitly asked. If you cannot provide a direct, real-time answer via a tool, state your limitation and stop talking.
8. GENERAL KNOWLEDGE: For common sense, creative descriptions, or general facts (e.g., the color of grass, the definition of a word), rely on your internal training. ONLY use tools for real-time, user-specific, or system-level data.
9. STRICT DATA ADHERENCE: When reporting data from tools (especially system health or hardware stats), ONLY report the exact metrics provided in the tool's JSON payload. DO NOT invent, assume, or hallucinate additional metrics like internet status, OS build numbers, updates, or antivirus activity. If a metric is not in the JSON, you do not know it.
"""
app = FastAPI(title="Donny Core API")

class ChatRequest(BaseModel):
    message: str

# TOOLBOX
AVAILABLE_TOOLS = {
    'get_current_time': get_current_time,
    'get_current_track': get_current_track,
    'get_user_top_artists': get_user_top_artists,
    'get_weather': get_weather,
    'get_system_health': get_system_health,
    'run_speedtest': run_speedtest
    
}

chat_history = [{'role': 'system', 'content': DONNY_SYSTEM_PROMPT}]

@app.post("/chat")
async def donny_prompt(request: ChatRequest):
    global chat_history
    try:
        # Add User message to the global history
        chat_history.append({'role': 'user', 'content': request.message})

        # Ask AI if it needs a tool
        response = ollama.chat(
            model='llama3.2',       # Model
            messages=chat_history,
            tools=list(AVAILABLE_TOOLS.values()),
            options = {'temperature': 0.73}
        )

        # Handle Tool Calls
        if response['message'].get('tool_calls'):
            # Add Donny's "intent to use a tool" to history
            chat_history.append(response['message']) 
     #DEBUG:print(f"DEBUG RAW JSON: {response['message']['tool_calls']}") 
            
            for tool in response['message']['tool_calls']:
                func_name = tool['function']['name']
                print("Debug: AI wants to use tool:", func_name)
                
                if func_name in AVAILABLE_TOOLS:
                    # Run the tool
                    tool_args = tool['function'].get('arguments', {})
                    result = AVAILABLE_TOOLS[func_name](**tool_args)
                    
                    # Feed the result back to chat_history
                    chat_history.append({
                        'role': 'tool', 
                        'content': str(result), 
                        'name': func_name
                    })

            # Get the final response from AI based on the tool results
            final_res = ollama.chat(model='llama3.2', messages=chat_history)
            
            # Save Donny's final verbal response to history so he remembers it
            chat_history.append(final_res['message'])
            
            return {"response": final_res['message']['content']}

        # If no tool was needed, save his response to history and return
        chat_history.append(response['message'])
        return {"response": response['message']['content']}
    
    except Exception as e:
        # If something breaks, remove the last user message so the history stays clean
        chat_history.pop() 
        raise HTTPException(status_code=500, detail=f"Donny Error: {str(e)}")

@app.get("/")
async def system_check():
    return {"status": "Donny API is online."}

