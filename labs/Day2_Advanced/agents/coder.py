from langchain_core.prompts import ChatPromptTemplate
from state import Task, TaskStatus
from utils.llm import get_llm
from datetime import datetime
import re


class CoderAgent:
    def __init__(self):
        self.llm = get_llm(temperature=0.2)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert software developer. Generate clean, well-documented code.

            Guidelines:
            - Write production-ready code
            - Include proper error handling
            - Add comments and docstrings
            - Follow best practices
            - Consider edge cases"""),
            ("human", """Task: {task_description}

            Context/Requirements:
            {context}

            Generate the code to complete this task. Include:
            1. Complete code implementation
            2. Brief explanation
            3. Usage examples if applicable"""),
        ])

    def generate_code(self, task: Task, context: dict = None) -> dict:
        """Generate code for a task."""
        context_str = ""
        if context:
            context_str = f"Research findings: {context.get('research', '')}\n"
            context_str += f"Previous code: {context.get('code', '')}"

        chain = self.prompt | self.llm

        try:
            response = chain.invoke({
                "task_description": task["description"],
                "context": context_str,
            })

            code_content = response.content
            code_blocks = self._extract_code_blocks(code_content)

            return {
                "task_id": task["id"],
                "code": code_blocks[0] if code_blocks else code_content,
                "explanation": self._extract_explanation(code_content),
                "status": TaskStatus.COMPLETED,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "task_id": task["id"],
                "code": "",
                "explanation": f"Code generation error: {str(e)}",
                "status": TaskStatus.FAILED,
                "timestamp": datetime.now().isoformat(),
            }

    def _extract_code_blocks(self, text: str) -> list:
        pattern = r"```(?:python|javascript|typescript|java|go|rust)?\n(.*?)```"
        return re.findall(pattern, text, re.DOTALL)

    def _extract_explanation(self, text: str) -> str:
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        return text.strip()
