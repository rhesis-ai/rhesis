import os

import streamlit as st
from client import _resolve_chatbot_params
from endpoint import stream_assistant_response_sync


def short_version(v: str) -> str:
    if not v:
        return ""
    if v.startswith("v_"):
        return f"v_{v[2:8]}"
    return v[:8]

# Must be the first Streamlit command
st.set_page_config(page_title="Insurance Assistant", page_icon="👩‍💼", layout="centered")


def display_experiment_pill(container):
    """Display the active experiment/version pill if resolved from Parameters.get()"""
    from rhesis.sdk import Parameters
    CHATBOT_PROJECT = os.getenv("RHESIS_CHATBOT_PROJECT", "chatbot-demo")
    parameters_environment = os.getenv(
        "RHESIS_PARAMETERS_ENVIRONMENT",
        os.getenv("RHESIS_PARAMETERS_LABEL", "default"),
    )
    try:
        params = Parameters.get(
            project=CHATBOT_PROJECT, environment=parameters_environment
        )
        version_chip = short_version(params.version)
        source_env = params.source_environment or params.source
        container.info(f"🧪 **Live Configuration:** {version_chip} via `{source_env}`")
    except Exception:
        # Silently fail, it will fall back to default env/values
        pass


def display_welcome_message(container):
    container.markdown("###  Welcome to your Insurance Assistant!")
    container.write("I'm here to help you with:")
    container.markdown("""
        - Insurance policy questions
        - Claims assistance
        - Coverage explanations
        - Insurance terminology
    """)


def display_example_buttons(container):
    container.markdown("### Try asking:")
    # Container for example buttons to isolate their column layout
    with container:
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("What business cover do I need?", key="btn1"):
                st.session_state.prompt = "What insurance do I need for my business?"
            if st.button("What is term life insurance?", key="btn4"):
                st.session_state.prompt = (
                    "What's the difference between term and whole life insurance?"
                )
        with col2:
            if st.button("How do I claim insurance?", key="btn2"):
                st.session_state.prompt = "How do I file an insurance claim?"
            if st.button("What is liability insurance?", key="btn5"):
                st.session_state.prompt = "What does liability insurance cover?"
        with col3:
            if st.button("How much home cover needed?", key="btn3"):
                st.session_state.prompt = "How much home insurance coverage do I need?"
            if st.button("What affects car insurance?", key="btn6"):
                st.session_state.prompt = "What affects my car insurance rates?"


def main():
    # Initialize session state variables
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "prompt" not in st.session_state:
        st.session_state.prompt = None

    # Create fixed containers for different sections
    header = st.container()
    buttons = st.container()
    separator = st.container()
    chat_history = st.container()

    # Header section
    with header:
        display_experiment_pill(header)
        st.title("Hi, I'm Rosalind 👩‍💼")
        if not st.session_state.messages:
            display_welcome_message(header)

    # Buttons section
    with buttons:
        display_example_buttons(buttons)

    # Separator
    with separator:
        st.markdown("---")

    # Chat history and interaction
    with chat_history:
        # Display chat history
        for message in st.session_state.messages:
            avatar = "👩‍💼" if message["role"] == "assistant" else "🧑"
            with st.chat_message(message["role"], avatar=avatar):
                st.write(message["content"])

    # Chat input at the bottom
    user_input = st.chat_input("Ask me anything about insurance!")

    # Handle both button clicks and direct input
    if user_input:
        st.session_state.prompt = user_input

    # Process any new message (from input or button)
    if st.session_state.prompt:
        prompt = st.session_state.prompt
        st.session_state.prompt = None  # Clear the prompt after using it

        # Display user message and add to history
        with st.chat_message("user", avatar="🧑"):
            st.write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get and display AI response, then add to history
        with st.chat_message("assistant", avatar="👩‍💼"):
            message_placeholder = st.empty()
            full_response = ""

            # Show loading spinner before streaming starts
            with st.spinner("Thinking..."):
                # Resolve parameters so they affect the stream
                params = _resolve_chatbot_params()
                
                # Get first chunk to ensure connection is established
                try:
                    # Pass conversation history (excluding the current user message we just added)
                    conversation_history = st.session_state.messages[:-1]
                    stream = stream_assistant_response_sync(
                        prompt, 
                        use_case=params.get("use_case", "travel"),
                        conversation_history=conversation_history,
                        mode=params.get("output_mode", "text"),
                        system_prompt_override=params.get("system_prompt"),
                        model=params.get("model"),
                        temperature=params.get("temperature", 0.7),
                        max_tokens=params.get("max_tokens", 1024),
                        context_strategy=params.get("context_strategy", "heuristic"),
                    )
                    first_chunk = next(stream)
                    full_response = first_chunk
                except StopIteration:
                    full_response = "I apologize, but I couldn't generate a response at this time."

            # Display first chunk
            message_placeholder.markdown(full_response + "▌")

            # Continue streaming remaining chunks
            try:
                for chunk in stream:
                    full_response += chunk
                    message_placeholder.markdown(full_response + "▌")
            except Exception:
                pass

            # Display final response without cursor
            message_placeholder.markdown(full_response)

            # Add assistant message to history after streaming is complete
            st.session_state.messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    main()
