from app.core.utils import call_llm
from app.modes.chapter.prompts import CODE_EXECUTION_PROMPT
import json
import re

class CodeExecutionAgent:
    def __init__(self):
        pass

    def enhance_code(self, original_code):
        """
        Enhances the code adding imports, visualization and ensuring runnability.
        Returns: { 'code': str, 'dependencies': list[str] }
        """
        prompt = CODE_EXECUTION_PROMPT.format(code=original_code)
        
        # Use call_llm utility
        # It returns (response_content, error)
        response, error = call_llm(prompt)
        
        if error:
            print(f"LLM Error in enhanced_code: {error}")
            return {"code": original_code, "dependencies": []}
        
        # Parse JSON from response
        try:
            # Simple cleanup to find JSON block
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data
            else:
                 # Fallback if no JSON found
                 return {"code": original_code, "dependencies": []}
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            return {"code": original_code, "dependencies": []}
