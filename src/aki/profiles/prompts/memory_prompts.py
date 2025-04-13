"""Prompts for memory management in conversations."""

INITIAL_SUMMARY_PROMPT = """
Create a natural conversation summary that combines detailed recent history with contextual background.

RECENT INTERACTIONS (Last 3-5 exchanges in detail):
{Keep these verbatim with full context and responses}

CONVERSATION CONTEXT:
Main Goal: {Primary objective or task}
Current Focus: {Specific current focus or subtask}

Background Summary:
- Key decisions and findings from earlier exchanges
- Important technical details discovered
- Relevant file paths and configurations discussed
- Tools used and their significant outcomes

Progress & Next Steps:
- What has been completed
- Current task status
- Planned next actions

Guidelines:
- Maintain verbatim detail of recent exchanges
- Keep technical context that's relevant to current focus
- Present information in a natural, conversational flow
- Preserve exact quotes for critical technical details
"""

EXTEND_SUMMARY_PROMPT = """
Current conversation state:
{existing_summary}

Extend this summary while maintaining natural conversation flow:

1. Add new interaction to RECENT INTERACTIONS:
   - Keep last 3-5 exchanges in full detail
   - Remove oldest detailed exchange if needed
   
2. Update CONVERSATION CONTEXT:
   - Revise current focus if changed
   - Add new key findings to background
   - Update progress and next steps
   
3. Maintain Continuity:
   - Ensure smooth transition between detailed and summarized content
   - Keep technical details accurate and accessible
   - Update without breaking ongoing conversation flow

Remember:
- Prioritize recent conversation detail
- Keep critical technical context
- Maintain natural dialogue flow
- Preserve exact technical details and paths
"""
