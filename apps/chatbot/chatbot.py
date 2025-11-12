import streamlit as st
from endpoint import stream_assistant_response

# Must be the first Streamlit command
st.set_page_config(page_title="Marvin - Coding Assistant", page_icon="🤖", layout="centered")


def display_welcome_message(container):
    container.markdown("###  Welcome to Marvin, your existentially pessimistic coding assistant!")
    container.write("I'm here to reluctantly help you with:")
    container.markdown("""
        - Writing code (though I question why you bother)
        - Debugging programs (fixing meaningless digital constructs)
        - Code reviews (critiquing futile attempts at order)
        - Programming questions (about our doomed digital existence)
    """)


def display_example_buttons(container):
    container.markdown("### Try asking (if you must):")
    # Container for example buttons to isolate their column layout
    with container:
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Fix my Python bug", key="btn1"):
                st.session_state.prompt = (
                    "I have a Python bug in my code, can you help me debug it?"
                )
            if st.button("Write a function", key="btn4"):
                st.session_state.prompt = "Can you write a function to sort a list of dictionaries?"
        with col2:
            if st.button("Code review help", key="btn2"):
                st.session_state.prompt = "Can you review my code and suggest improvements?"
            if st.button("Explain this algorithm", key="btn5"):
                st.session_state.prompt = "Can you explain how quicksort works?"
        with col3:
            if st.button("Best practices?", key="btn3"):
                st.session_state.prompt = "What are some Python best practices I should follow?"
            if st.button("Optimize my code", key="btn6"):
                st.session_state.prompt = "How can I make this code more efficient?"


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
        st.title("Hi, I'm Marvin 🤖")
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
            avatar = "🤖" if message["role"] == "assistant" else "🧑"
            with st.chat_message(message["role"], avatar=avatar):
                st.write(message["content"])

    # Chat input at the bottom
    user_input = st.chat_input("Ask me about coding... if you must...")

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
        with st.chat_message("assistant", avatar="🤖"):
            message_placeholder = st.empty()
            full_response = ""

            # Show loading spinner before streaming starts
            with st.spinner("Thinking..."):
                # Get first chunk to ensure connection is established
                try:
                    # Pass conversation history (excluding the current user message we just added)
                    conversation_history = st.session_state.messages[:-1]
                    stream = stream_assistant_response(
                        prompt, use_case="coding", conversation_history=conversation_history
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
            except:
                pass

            # Display final response without cursor
            message_placeholder.markdown(full_response)

            # Add assistant message to history after streaming is complete
            st.session_state.messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    main()
