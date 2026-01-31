# Phase 03: Code Flow Tracing Improvements

This phase addresses Priority 3 from the improvement plan: improving code flow tracing. The "code_flow" question category is the hardest, with failures on ripgrep and fastapi. The agent struggles to trace request → handler → service → database flows. We'll add dedicated prompting and consider a call graph tracing tool.

## Tasks

- [x] Add CODE_FLOW_PROMPT template to `src/prompts/__init__.py`: *(Completed: Added CODE_FLOW_PROMPT with 4-step workflow for code flow tracing)*
  - Create a new constant `CODE_FLOW_PROMPT` with specialized instructions:
    ```python
    CODE_FLOW_PROMPT = """Answer this code flow question about the codebase:

    {question}

    ## MANDATORY WORKFLOW FOR CODE FLOW QUESTIONS

    **STEP 1: FIND ENTRY POINT**
    - Run `find_entry_points` to locate where execution begins
    - Read the main entry file with `read_file`

    **STEP 2: TRACE IMPORTS**
    - Use `get_imports` on the entry point file
    - Identify which local modules are imported

    **STEP 3: FOLLOW THE CHAIN**
    - Read each file in the call chain using `read_file`
    - Look for function calls that lead to the next step
    - Document: File A:line → calls → File B:line → calls → ...

    **STEP 4: DOCUMENT THE FLOW**
    - Present the flow as a numbered sequence
    - Each step must have a file:line citation
    - Explain what happens at each step

    ## OUTPUT FORMAT

    **Files Read:** (REQUIRED - list ALL files in the trace)
    - [entry.py]
    - [handler.py]
    - [service.py]

    **Flow Trace:**
    1. `entry.py:15` - Execution starts here when...
    2. `entry.py:23` - Calls `handle_request()` in...
    3. `handler.py:45` - Receives request, validates...
    4. ...continue the chain...

    **Summary:** [One paragraph explaining the complete flow]

    ## QUESTION

    {question}
    """
    ```

- [x] Add code_flow question detection in `CodebaseOnboardingAgent.ask()` in `src/agent.py`: *(Already implemented: `_is_code_flow_question()` at lines 461-477 with expanded keywords including "walk through", "execution path", "called in what order", "sequence of calls". Used in both `ask()` at line 485 and `stream_ask()` at line 1025)*
  - Before calling `self._run()`, detect if the question is about code flow
  - Check for keywords: "trace", "flow", "how does...work", "what happens when", "execution path", "call sequence"
  - If detected, use CODE_FLOW_PROMPT instead of DEEP_DIVE_PROMPT
  - Example implementation:
    ```python
    def _is_code_flow_question(self, question: str) -> bool:
        flow_keywords = ["trace", "flow", "what happens", "how does", "execution", "call sequence", "step by step"]
        q_lower = question.lower()
        return any(kw in q_lower for kw in flow_keywords)
    ```

- [ ] Add code_flow specific question templates to `src/eval/questions.py`:
  - Add 3-4 new code_flow templates with clear tracing requirements:
    - "Trace what happens when {main_function} is called from start to finish"
    - "What is the execution path from the entry point to {feature_area}?"
    - "Walk through the code flow when a user performs {action}"
  - Set `min_citations=4` for code_flow questions (need multiple files)
  - Set `expected_tools=["find_entry_points", "read_file", "get_imports"]`

- [ ] Run evaluation on repos with known code_flow failures:
  - Execute: `python run_multi_eval.py --repos ripgrep,fastapi --diverse`
  - Focus on code_flow category questions
  - Verify the flow traces include multiple file citations
  - Check that answers show clear step-by-step sequences
  - Save results to `Auto Run Docs/Initiation/Working/phase03_eval_results.txt`
