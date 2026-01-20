import base64

import streamlit as st
from endpoint import get_response_generator

# Must be the first Streamlit command
st.set_page_config(page_title="Insurance Assistant", page_icon="👩‍💼", layout="centered")


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
    if "uploaded_images" not in st.session_state:
        st.session_state.uploaded_images = []

    # Create fixed containers for different sections
    header = st.container()
    buttons = st.container()
    separator = st.container()
    chat_history = st.container()

    # Header section
    with header:
        st.title("Hi, I'm Rosalind 👩‍💼")
        if not st.session_state.messages:
            display_welcome_message(header)

    # Buttons section
    with buttons:
        display_example_buttons(buttons)

    # Separator
    with separator:
        st.markdown("---")

    # Sidebar for image features
    with st.sidebar:
        st.header("🖼️ Image Features")

        # Tab for image upload/analysis
        tab1, tab2, tab3 = st.tabs(["📤 Analyze Image", "🎨 Generate Image", "✏️ Edit Image"])

        with tab1:
            st.subheader("Upload Images")
            uploaded_files = st.file_uploader(
                "Upload images to analyze",
                type=["jpg", "jpeg", "png", "gif", "webp"],
                accept_multiple_files=True,
                key="image_uploader",
            )

            if uploaded_files:
                st.session_state.uploaded_images = uploaded_files
                st.success(f"✅ {len(uploaded_files)} image(s) uploaded")
                for img in uploaded_files:
                    st.image(img, caption=img.name, use_container_width=True)

            if st.button("🗑️ Clear Images", key="clear_images"):
                st.session_state.uploaded_images = []
                st.rerun()

        with tab2:
            st.subheader("Generate Image")
            st.info(
                "💡 **Note:** Requires image generation model (e.g., Gemini Imagen). "
                "Set `IMAGE_GENERATION_MODEL=gemini` and "
                "`IMAGE_GENERATION_MODEL_NAME=imagen-4.0-generate-001` in your environment."
            )
            image_prompt = st.text_area(
                "Describe the image to generate",
                placeholder="A modern insurance office with clean design...",
                key="image_prompt",
            )

            col1, col2 = st.columns(2)
            with col1:
                num_images = st.selectbox("Number of images", [1, 2, 3, 4], index=0)
            with col2:
                image_size = st.selectbox("Size", ["1024x1024", "512x512", "256x256"], index=0)

            if st.button("🎨 Generate", key="generate_btn", disabled=not image_prompt):
                with st.spinner("Generating image..."):
                    try:
                        response_generator = get_response_generator()
                        result = response_generator.generate_image(
                            prompt=image_prompt, n=num_images, size=image_size
                        )

                        # Normalize to list
                        images = [result] if isinstance(result, str) else result

                        st.success(f"✅ Generated {len(images)} image(s)")
                        for i, img_url in enumerate(images, 1):
                            st.image(
                                img_url, caption=f"Generated Image {i}", use_container_width=True
                            )
                    except Exception as e:
                        error_msg = str(e)
                        st.error(f"❌ Error: {error_msg}")

                        # Provide helpful guidance
                        is_generation_error = (
                            "doesn't support image generation" in error_msg
                            or "BadRequestError" in error_msg
                        )
                        if is_generation_error:
                            st.warning(
                                "**Image generation requires a specific model.** "
                                "Please set these environment variables:\\n\\n"
                                "```\\n"
                                "IMAGE_GENERATION_MODEL=gemini\\n"
                                "IMAGE_GENERATION_MODEL_NAME=imagen-4.0-generate-001\\n"
                                "GEMINI_API_KEY=your-api-key\\n"
                                "```"
                            )

        with tab3:
            st.subheader("Edit Image")
            st.info(
                "💡 **Note:** Upload an image and describe how you want it edited. "
                "Uses AI to modify the image according to your instructions."
            )

            # Image upload for editing
            edit_image = st.file_uploader(
                "Upload image to edit",
                type=["jpg", "jpeg", "png", "gif", "webp"],
                key="edit_image_uploader",
            )

            if edit_image:
                st.image(edit_image, caption="Original Image", use_container_width=True)

            # Edit instructions
            edit_prompt = st.text_area(
                "Describe how to edit the image",
                placeholder="Change the color to blue, remove the background, add a sunset...",
                key="edit_prompt",
                disabled=not edit_image,
            )

            if st.button(
                "✏️ Edit Image", key="edit_btn", disabled=not edit_image or not edit_prompt
            ):
                with st.spinner("Editing image..."):
                    try:
                        # Convert image to base64
                        img_bytes = edit_image.read()
                        edit_image.seek(0)  # Reset file pointer
                        encoded = base64.b64encode(img_bytes).decode("utf-8")

                        response_generator = get_response_generator()
                        result = response_generator.edit_image(
                            image_data=encoded, edit_prompt=edit_prompt
                        )

                        st.success("✅ Image edited successfully!")
                        st.image(result, caption="Edited Image", use_container_width=True)

                    except Exception as e:
                        error_msg = str(e)
                        st.error(f"❌ Error: {error_msg}")

                        if "doesn't support image editing" in error_msg:
                            st.warning(
                                "**Image editing is currently experimental.** "
                                "This feature uses AI image generation based on the "
                                "original image and your editing instructions."
                            )

    # Chat history and interaction
    with chat_history:
        # Display chat history
        for message in st.session_state.messages:
            avatar = "👩‍💼" if message["role"] == "assistant" else "🧑"
            with st.chat_message(message["role"], avatar=avatar):
                # Display images if present
                if "images" in message:
                    cols = st.columns(min(len(message["images"]), 3))
                    for idx, img_data in enumerate(message["images"]):
                        with cols[idx % 3]:
                            st.image(img_data, use_container_width=True)
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

        # Get uploaded images if any
        uploaded_images = st.session_state.uploaded_images
        has_images = len(uploaded_images) > 0

        # Display user message and add to history
        with st.chat_message("user", avatar="🧑"):
            if has_images:
                # Display uploaded images in columns
                cols = st.columns(min(len(uploaded_images), 3))
                for idx, img_file in enumerate(uploaded_images):
                    with cols[idx % 3]:
                        st.image(img_file, use_container_width=True)
            st.write(prompt)

        # Add to message history
        user_message = {"role": "user", "content": prompt}
        if has_images:
            user_message["images"] = uploaded_images
        st.session_state.messages.append(user_message)

        # Get and display AI response
        with st.chat_message("assistant", avatar="👩‍💼"):
            message_placeholder = st.empty()
            full_response = ""

            # Show loading spinner before streaming starts
            with st.spinner("Thinking..."):
                try:
                    response_generator = get_response_generator()
                    conversation_history = st.session_state.messages[:-1]

                    if has_images:
                        # Convert images to base64 for multimodal response
                        image_data_list = []
                        for img_file in uploaded_images:
                            img_bytes = img_file.read()
                            img_file.seek(0)  # Reset file pointer for display
                            encoded = base64.b64encode(img_bytes).decode("utf-8")
                            image_data_list.append(encoded)

                        # Get multimodal response (non-streaming)
                        full_response = response_generator.get_multimodal_response(
                            message=prompt,
                            conversation_history=conversation_history,
                            image_data=image_data_list,
                        )

                        # Clear uploaded images after processing
                        st.session_state.uploaded_images = []
                    else:
                        # Standard streaming response for text-only
                        stream = response_generator.stream_assistant_response(
                            prompt, conversation_history=conversation_history
                        )
                        first_chunk = next(stream)
                        full_response = first_chunk
                except StopIteration:
                    full_response = "I apologize, but I couldn't generate a response at this time."
                except Exception as e:
                    full_response = f"I apologize, but I encountered an error: {str(e)}"

            # Display response
            if has_images:
                # For multimodal, display complete response
                message_placeholder.markdown(full_response)
            else:
                # For text-only, stream the response
                message_placeholder.markdown(full_response + "▌")

                try:
                    for chunk in stream:
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                except Exception:
                    pass

                message_placeholder.markdown(full_response)

            # Add assistant message to history
            st.session_state.messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    main()
