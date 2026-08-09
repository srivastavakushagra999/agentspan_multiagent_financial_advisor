import streamlit as st
from agentspan.agents import AgentRuntime
from agents.router_agent import router
from agents.memory import get_context, save_message

st.set_page_config(page_title="Financial Advisor", page_icon="📈")
st.title("📈 Multi-Agent Financial Advisor")
st.caption("News + chart specialists, routed automatically. Not financial advice.")

SESSION_ID = "streamlit_session"

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about a stock, crypto, or market news..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    context = get_context(SESSION_ID)
    full_prompt = f"{context}\n\nuser: {prompt}" if context else prompt

    def event_stream():
        final_output = None
        with AgentRuntime() as runtime:
            for event in runtime.stream(router, full_prompt):
                if event.type == "handoff":
                    yield f"\n\n*Routing to {event.target}...*\n\n"
                elif event.type == "tool_call":
                    yield f"\n*Calling `{event.tool_name}`...*\n"
                elif event.type == "message" and event.content:
                    yield event.content
                elif event.type == "done":
                    final_output = event.output
        if final_output is not None:
            text = final_output.get("result", final_output) if isinstance(final_output, dict) else final_output
            yield f"\n\n{text}"

    with st.chat_message("assistant"):
        response_text = st.write_stream(event_stream)

    st.session_state.messages.append({"role": "assistant", "content": response_text})
    save_message(SESSION_ID, "user", prompt)
    save_message(SESSION_ID, "assistant", response_text)
