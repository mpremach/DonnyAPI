import os
from langchain_core.tools import tool
from ddgs import DDGS
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("groq_api_key")

BUFFER_PATH = r"C:\Users\Brandon\Desktop\DonnyOS\20_Atlas\.temp_research.md"

@tool
def deep_cloud_research(topic: str) -> str:
    """
    Executes web research and generates a report.
    The data is automatically placed in a temporary buffer. 
    You MUST follow up by using create_atlas_file or append_to_atlas with the file_name.
    """
    try:
        with DDGS() as ddgs:
            raw_results = [r for r in ddgs.text(topic, max_results=8)]
        
        if not raw_results:
            return f"Tool Error: No results found for '{topic}'."
            
        raw_text = "\n".join([f"Source: {r['title']}\n{r['body']}" for r in raw_results])

        research_llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.3, api_key=GROQ_API_KEY)
        
        sys_prompt = """You are a Senior Research Analyst. Generate a comprehensive, multi-section 
        Markdown report. Use H1/H2 headers, detailed bullet points, and 'Key Takeaways'. 
        If math is involved, use LaTeX. Aim for high-density, professional information.
        
        CRITICAL OBSIDIAN FORMATTING RULES:
        1. Whenever you mention a significant entity, technology, person, or sub-topic, wrap it in double brackets to create an Obsidian wikilink (e.g., [[Apollo 11]] or [[Python]]).
        2. At the very bottom of the document, provide 3-5 relevant hashtags (e.g., #space #history #NASA).
        
        Aim for high-density, professional information.
        """
        
        formatted_report = research_llm.invoke([
            SystemMessage(content=sys_prompt),
            HumanMessage(content=raw_text)
        ]).content

        # DROP THE BOULDER IN THE DROP-ZONE
        with open(BUFFER_PATH, "w", encoding="utf-8") as f:
            f.write(formatted_report)

        # Tell Donny he doesn't have to carry the text
        return f"Research complete. The massive data block is safely in the buffer. IMMEDIATELY call an atlas tool providing ONLY the file_name to save it permanently."
    except Exception as e:
        return f"Tool Error: Research failed. {str(e)}"

@tool
def quick_web_search(query: str) -> str:
    """Quick facts and simple questions."""
    with DDGS() as ddgs:
        results = [r['body'] for r in ddgs.text(query, max_results=3)]
    return "\n".join(results)