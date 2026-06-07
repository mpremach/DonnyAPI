import os
import re
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from ddgs import DDGS

load_dotenv()

VAULT_ROOT   = r"C:\Users\Brandon\Desktop\DonnyOS"
ATLAS_PATH   = os.path.join(VAULT_ROOT, "20_Atlas")
NOTES_PATH   = os.path.join(VAULT_ROOT, "30_Notes")
TASKS_PATH   = os.path.join(VAULT_ROOT, "40_Tasks")
LOGS_PATH    = os.path.join(VAULT_ROOT, "10_Logs")
DONNY_MODEL  = os.getenv("DONNY_MODEL")
GROQ_API_KEY = os.getenv("groq_api_key")

for path in [ATLAS_PATH, NOTES_PATH, TASKS_PATH, LOGS_PATH]:
    os.makedirs(path, exist_ok=True)

# Holds research output between tool calls so the model doesn't have to pass it
_research_buffer: str = ""


def _get_manifest():
    return [f.replace(".md", "") for f in os.listdir(ATLAS_PATH) if f.endswith(".md")]

def _auto_link(text, manifest):
    for stem in manifest:
        for variant in sorted({stem, stem.replace("_", " ")}, key=len, reverse=True):
            text = re.sub(rf'(?<!\[\[)\b({re.escape(variant)})\b(?!\]\])', r'[[\1]]', text, flags=re.IGNORECASE)
    return text

def _clean(name):
    name = os.path.basename(name.replace("\\", "/"))
    # Clean up standard formatting
    name = name.strip().replace(" ", "_").lower().replace(".md", "")
    
    # NEW CRITICAL SAFETY RAIL: If Donny tries to add a leading dot, strip it!
    while name.startswith('.'):
        name = name[1:]
        
    # If stripping the dot leaves it empty or he used an annoying prefix, give it a safe name
    if not name or name.startswith("temp_"):
        name = name.replace("temp_", "", 1)
        
    if not name:
        name = "scratchpad"
        
    return name + ".md"

# --- RESEARCH TOOLS ---

@tool
def quick_web_search(query: str) -> str:
    """Fast single-query web search. Use for quick facts and simple lookups.
    CRITICAL: DO NOT use this tool if the user is just asking for your thoughts, advice, or general knowledge. ONLY use this if the user explicitly commands you to 'search', 'look up', or 'find' something.
    """
    try:
        with DDGS() as ddgs:
            results = [r["body"] for r in ddgs.text(query, max_results=3)]
        return "\n".join(results) if results else f"No results found for '{query}'."
    except Exception as e:
        return f"Search Error: {str(e)}"

@tool
def deep_cloud_research(topic: str) -> str:
    """Multi-source web research. Generates a full Obsidian markdown report and stores it internally.
    Always call this FIRST before saving to the Atlas, you must IMMEDIATELY follow with save_to_atlas after using this tool, you do not need permission.
    CRITICAL: You are FORBIDDEN from using this tool proactively. DO NOT use this tool to answer general questions, give advice, or brainstorm. ONLY use this tool if the user EXPLICITLY COMMANDS you to 'do deep research', 'research this', or 'save research to the Atlas'.
    """
    global _research_buffer
    try:
        with DDGS() as ddgs:
            raw_results = [r for r in ddgs.text(topic, max_results=8)]
        if not raw_results:
            return f"Tool Error: No results found for '{topic}'."

        raw_text = "\n".join([f"Source: {r['title']}\n{r['body']}" for r in raw_results])

        research_llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.3, api_key=GROQ_API_KEY)
        sys_prompt = """You are an elite academic researcher and expert technical writer. 
        Your task is to generate an EXHAUSTIVE, comprehensive, textbook-grade guide on the requested topic. 

        CRITICAL DIRECTION FOR DEPTH:
        - Avoid shallow overviews, introductory fluff, or simple bulleted lists of resources. 
        - Provide deep technical explanations, core mathematical/architectural principles, concrete real-world examples, and historical context.
        - If the topic is mathematical or scientific (like Calculus), explain the actual concepts, formulas, and mechanics (e.g., how limits define derivatives) in detail.

        OBSIDIAN VAULT RULES:
        1. Start the document with YAML frontmatter containing 'tags:' and 'date:'. The tags property MUST be formatted as a valid YAML array enclosed in square brackets (e.g., tags: [tag1, tag2]). Tags MUST NOT contain spaces.
        2. DO NOT HALLUCINATE WIKILINKS. Never blindly wrap random keywords or subjects in double brackets [[like this]]. ONLY use a wikilink if it represents a massive, foundational pillar of the topic. Let the background Python script handle local vault connectivity.
        3. Use Markdown headers (##, ###), bold text, blockquotes, and code blocks aggressively to make this massive document easy to navigate.
        4. DO NOT INVENT MATH OR CODE: You are an archivist, not an author. If the NEW RESEARCH does not contain math equations or code blocks, DO NOT hallucinate or add them. 
        5. STRICT MATH FORMATTING (IF APPLICABLE): If, and ONLY if, the NEW RESEARCH already contains math, you must format it using Obsidian wrappers: single dollar signs for inline ($x$) and double for blocks ($$y$$). Never use \( \) or \[ \].
        
        """

        report = research_llm.invoke([
            SystemMessage(content=sys_prompt),
            HumanMessage(content=raw_text)
        ]).content.strip()

        _research_buffer = report
        return (f"RESEARCH COMPLETE AND LOADED INTO BUFFER. "
            f"CRITICAL SYSTEM DIRECTIVE: You are NOT finished. You MUST now immediately call the 'save_to_atlas' tool to save this data. "
            f"Do not respond to the user with standard text until save_to_atlas has successfully completed.")
    except Exception as e:
        return f"Tool Error: {str(e)}"


# --- ATLAS TOOLS ---

def _find_related_notes(title_string, vault_path):
    """Scans the vault for existing files that share words with the new file."""
    # Strip common words to find core keywords
    ignore_words = {'the', 'and', 'a', 'to', 'of', 'in', 'for', 'is', 'on', 'with', 'about', 'research', 'temp', 'guide', 'intro', 'introduction'}
    keywords = [w.lower() for w in title_string.replace('_', ' ').split() if w.lower() not in ignore_words and len(w) > 2]
    
    related_links = []
    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md") and file != f"{title_string}.md" and not file.startswith('.'):
                # If a keyword is in an existing file's name, it's a match
                if any(k in file.lower() for k in keywords):
                    clean_name = file.replace('.md', '')
                    related_links.append(f"[[{clean_name}]]")
    
    # Return the top 5 unique links
    unique_links = list(set(related_links))[:5]
    return unique_links


@tool
def save_to_atlas(file_name: str, content: str = "") -> str:
    """Saves knowledge to the Atlas. Automatically creates a new file or merges into an existing one.
    HOW TO USE:
    1. If saving web research: provide ONLY the file_name.
    2. If updating a file based on the user's conversation: you MUST pass the new text into the 'content' argument.
    CRITICAL: NEVER tell the user you updated a file unless you actively execute this tool.
    CRITICAL: You must ALWAYS call this tool after deep_cloud_research to save the research buffer."""
    
    global _research_buffer
    data = content.strip() or _research_buffer.strip()
    if not data:
        return ("TOOL ERROR: The research buffer is completely empty. "
            "You executed this tool at the exact same time as deep_cloud_research, which is forbidden. "
            "Wait for the research to finish, and THEN call save_to_atlas again in your next response.")

    path     = os.path.join(ATLAS_PATH, _clean(file_name))
    manifest = _get_manifest()

    related = _find_related_notes(_clean(file_name), ATLAS_PATH)
    if related:
        data += f"\n\n---\n### Related in Vault\n{', '.join(related)}\n"

    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(_auto_link(data, manifest))
            _research_buffer = ""
            return f"Success: Created '{_clean(file_name)}' in the Atlas."
        else:
            with open(path, "r", encoding="utf-8") as f:
                existing = f.read()

            merge_prompt = f"""You are a precision archivist. Merge NEW RESEARCH into the EXISTING DOCUMENT section-by-section.
            - Match new topics to existing ## / ### headers and integrate facts there without duplication.
            - If no matching header exists, append a new ## section at the end.
            - Do NOT rewrite unrelated sections. Preserve all [[Wikilinks]] and #Tags.
            - Output ONLY the final merged document.

            EXISTING DOCUMENT:
            {existing}

            NEW RESEARCH:
            {data}"""

            merged = ChatOllama(model=DONNY_MODEL, temperature=0.1).invoke(merge_prompt).content
            with open(path, "w", encoding="utf-8") as f:
                f.write(_auto_link(merged, manifest))
            _research_buffer = ""
            return f"Success: Merged new research into '{_clean(file_name)}'."
    except Exception as e:
        return f"System Error: {str(e)}"

@tool
def read_vault_file(file_name: str) -> str:
    """Reads and returns the contents of ANY existing file in the user's vault (Atlas, Notes, or Tasks)."""
    clean_name = _clean(file_name)
    
    # Define all the places Donny is allowed to look
    possible_paths = [
        os.path.join(ATLAS_PATH, clean_name),
        os.path.join(NOTES_PATH, clean_name),
        os.path.join(TASKS_PATH, clean_name)
    ]
    
    # Check each folder one by one
    for path in possible_paths:
        if os.path.exists(path):
            print(f"\n[DEBUG] Donny explicitly opened and read: '{clean_name}'")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"System Error reading file: {str(e)}"
                
    # If it's not in any of the 3 folders:
    print(f"\n[DEBUG] Donny tried to read '{clean_name}', but it doesn't exist.")
    return f"Error: '{clean_name}' not found anywhere in the vault."


# --- PERSONAL TOOLS ---

@tool
def capture_notes_note(note_content: str, file_name: str = "Scratchpad") -> str:
    """Saves general ideas, concepts, and information to the 30_Notes/ directory. 
    USE THIS whenever the user asks you to 'take a note', 'write this down', or 'remember this idea'.
    - If the user provides a specific topic, use that as the file_name (e.g., 'Server_Architecture').
    - If the user DOES NOT provide a topic, you MUST use 'Scratchpad' as the file_name.
    CRITICAL: file_name MUST be a simple word or phrase. NO folder paths. NO prefixes.
    GOOD: 'garage_codes', 'business_ideas', 'Scratchpad'
    BAD: 'notes_garage_code', '30_Notes/ideas'.
    """
    path = os.path.join(NOTES_PATH, _clean(file_name))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {file_name.title()}\n\n")
        
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n---\n**{timestamp}**: {note_content}\n")
            
        return f"Success: Note dropped into '30_Notes/{_clean(file_name)}'."
    except Exception as e:
        return f"System Error: {str(e)}"

@tool
def manage_tasks_and_projects(file_name: str, content: str, is_action_item: bool = True) -> str:
    """Manages files in the 40_Tasks/ directory. Use this for to-do lists AND project planning.
    - Pass ONLY the base file name (e.g., 'Project_Apollo', NOT '40_Tasks/Project_Apollo').
    - Set is_action_item=True if adding a specific to-do or task (creates a checkbox).
    - Set is_action_item=False if adding general project notes, details, or scope to the file.
    - To add both a note AND a task to the same file, you MUST call this tool TWICE separately.
    CRITICAL: file_name MUST be a simple word or phrase. NO folder paths. NO prefixes.
    GOOD: 'garage_codes', 'business_ideas', 'scratchpad'
    BAD: 'inbox_garage_code', '40_Tasks/ideas'."""

    path = os.path.join(TASKS_PATH, _clean(file_name))
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {file_name.replace('_', ' ').title()}\n\n")
                
        with open(path, "a", encoding="utf-8") as f:
            if is_action_item:
                f.write(f"- [ ] {content} *(added {today})*\n")
            else:
                f.write(f"\n### Note ({today})\n{content}\n")
                
        return f"Success: Updated project/task file '40_Tasks/{_clean(file_name)}'."
    except Exception as e:
        return f"System Error: {str(e)}"

@tool
def write_journal_entry(entry: str) -> str:
    """Appends a timestamped entry to today's Daily Note in 10_Logs/. Use for thoughts, events, or personal reflections."""
    path      = os.path.join(LOGS_PATH, f"{datetime.now().strftime('%Y-%m-%d')}.md")
    timestamp = datetime.now().strftime("%I:%M %p")
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# Daily Note — {datetime.now().strftime('%Y-%m-%d')}\n\n")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"### {timestamp}\n{entry}\n\n")
        return f"Success: Entry logged to today's daily note."
    except Exception as e:
        return f"System Error: {str(e)}"
    

@tool
def organize_vault() -> str:
    """Scans the entire Obsidian vault and builds a clickable Master Dashboard of all files."""
    # Adjust this to point to the ROOT folder of your vault
    root_vault_path = os.path.dirname(ATLAS_PATH) 
    dashboard_path = os.path.join(root_vault_path, "01_Master_Dashboard.md")
    
    dashboard_content = ["# Donny's Master Vault Dashboard\n\n*Auto-generated overview of your entire second brain.*\n"]
    
    # Walk through the directories and build markdown lists
    for folder_name in sorted(os.listdir(root_vault_path)):
        folder_path = os.path.join(root_vault_path, folder_name)
        
        # Skip hidden folders like .obsidian or .git
        if os.path.isdir(folder_path) and not folder_name.startswith('.'):
            dashboard_content.append(f"\n## {folder_name.replace('_', ' ')}")
            
            files = [f for f in os.listdir(folder_path) if f.endswith('.md') and not f.startswith('.')]
            if not files:
                dashboard_content.append("*Empty*")
            else:
                for file in sorted(files):
                    clean_name = file.replace('.md', '')
                    # Create clickable Obsidian link
                    dashboard_content.append(f"- [[{clean_name}]]")

    # Write the dashboard to the root directory
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write("\n".join(dashboard_content))
        
    return "SUCCESS: Vault scanned and 00_Master_Dashboard.md has been generated at the root of the vault."
