import base64

import streamlit as st
from endpoint import get_response_generator

# Must be the first Streamlit command
st.set_page_config(page_title="Insurance Assistant", page_icon="🏢", layout="wide")

# Custom CSS for larger tab titles
st.markdown(
    """
    <style>
    /* Increase tab title font size */
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.2rem;
        font-weight: 500;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def initialize_session_state():
    """Initialize all session state variables for each tab"""
    # Text chatbot state
    if "text_messages" not in st.session_state:
        st.session_state.text_messages = []
    if "text_prompt" not in st.session_state:
        st.session_state.text_prompt = None

    # Damage assessment state
    if "damage_messages" not in st.session_state:
        st.session_state.damage_messages = []
    if "damage_prompt" not in st.session_state:
        st.session_state.damage_prompt = None
    if "damage_images" not in st.session_state:
        st.session_state.damage_images = []

    # Annotation tools state
    if "annotation_quick_prompt" not in st.session_state:
        st.session_state.annotation_quick_prompt = ""
    if "annotation_process_now" not in st.session_state:
        st.session_state.annotation_process_now = False


def display_chat_history(messages, avatar_assistant="👩‍💼"):
    """Display chat history for any tab"""
    for message in messages:
        avatar = avatar_assistant if message["role"] == "assistant" else "🧑"
        with st.chat_message(message["role"], avatar=avatar):
            if "images" in message:
                cols = st.columns(min(len(message["images"]), 3))
                for idx, img_data in enumerate(message["images"]):
                    with cols[idx % 3]:
                        st.image(img_data, width="stretch")
            st.write(message["content"])


def process_text_response(prompt, messages, message_placeholder):
    """Process a text-only response with streaming"""
    full_response = ""
    try:
        response_generator = get_response_generator()
        conversation_history = messages[:-1] if messages else []

        stream = response_generator.stream_assistant_response(
            prompt, conversation_history=conversation_history
        )
        first_chunk = next(stream)
        full_response = first_chunk
    except StopIteration:
        full_response = "I apologize, but I couldn't generate a response at this time."
        message_placeholder.markdown(full_response)
        return full_response
    except Exception as e:
        full_response = f"I apologize, but I encountered an error: {str(e)}"
        message_placeholder.markdown(full_response)
        return full_response

    message_placeholder.markdown(full_response + "▌")

    try:
        for chunk in stream:
            full_response += chunk
            message_placeholder.markdown(full_response + "▌")
    except Exception:
        pass

    message_placeholder.markdown(full_response)
    return full_response


def process_multimodal_response(prompt, messages, images, message_placeholder):
    """Process a multimodal response with images"""
    full_response = ""
    try:
        response_generator = get_response_generator()
        conversation_history = messages[:-1] if messages else []

        image_data_list = []
        for img_file in images:
            img_bytes = img_file.read()
            img_file.seek(0)
            encoded = base64.b64encode(img_bytes).decode("utf-8")
            image_data_list.append(encoded)

        full_response = response_generator.get_multimodal_response(
            message=prompt,
            conversation_history=conversation_history,
            image_data=image_data_list,
        )
    except Exception as e:
        full_response = f"I apologize, but I encountered an error: {str(e)}"

    message_placeholder.markdown(full_response)
    return full_response


# =============================================================================
# TAB 1: Insurance Assistant (Text Chatbot)
# =============================================================================
def render_text_chatbot():
    """Render the informational text chatbot"""
    st.markdown("## 👩‍💼 Meet Rosalind")

    # Welcome message for new users
    if not st.session_state.text_messages:
        st.markdown(
            """
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 1.5rem; border-radius: 12px; color: white; margin-bottom: 1rem;">
            <h4 style="margin: 0 0 0.5rem 0; color: white;">
                Welcome to your Insurance Assistant!</h4>
            <p style="margin: 0; opacity: 0.9;">I'm here to help you understand insurance policies, 
            file claims, and answer any coverage questions you may have.</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("#### I can help you with:")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("- 📋 Insurance policy questions")
            st.markdown("- 📝 Claims assistance")
        with col2:
            st.markdown("- 🔍 Coverage explanations")
            st.markdown("- 📚 Insurance terminology")

    # Example buttons
    st.markdown("#### Quick questions:")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💼 Business coverage", key="text_btn1"):
            st.session_state.text_prompt = "What insurance do I need for my business?"
        if st.button("🏥 Life insurance", key="text_btn4"):
            st.session_state.text_prompt = (
                "What's the difference between term and whole life insurance?"
            )
    with col2:
        if st.button("📄 File a claim", key="text_btn2"):
            st.session_state.text_prompt = "How do I file an insurance claim?"
        if st.button("⚖️ Liability coverage", key="text_btn5"):
            st.session_state.text_prompt = "What does liability insurance cover?"
    with col3:
        if st.button("🏠 Home insurance", key="text_btn3"):
            st.session_state.text_prompt = "How much home insurance coverage do I need?"
        if st.button("🚗 Car insurance", key="text_btn6"):
            st.session_state.text_prompt = "What affects my car insurance rates?"

    st.markdown("---")

    # Create a container for chat messages
    chat_container = st.container()

    # Chat input at bottom (Streamlit pins this to bottom automatically)
    user_input = st.chat_input("Ask me anything about insurance!", key="text_chat_input")

    if user_input:
        st.session_state.text_prompt = user_input

    # Display chat history and process new messages in the container
    with chat_container:
        # Display existing chat history
        display_chat_history(st.session_state.text_messages)

        # Process new prompt if exists
        if st.session_state.text_prompt:
            prompt = st.session_state.text_prompt
            st.session_state.text_prompt = None

            # Display user message
            with st.chat_message("user", avatar="🧑"):
                st.write(prompt)

            st.session_state.text_messages.append({"role": "user", "content": prompt})

            # Display assistant response with streaming
            with st.chat_message("assistant", avatar="👩‍💼"):
                message_placeholder = st.empty()
                with st.spinner("Thinking..."):
                    full_response = process_text_response(
                        prompt, st.session_state.text_messages, message_placeholder
                    )

            st.session_state.text_messages.append({"role": "assistant", "content": full_response})
            st.rerun()


# =============================================================================
# TAB 2: Auto Damage Assessment
# =============================================================================
def render_damage_assessment():
    """Render the auto damage assessment chatbot"""
    st.markdown("## 🚗 Auto Damage Assessment")

    # Info banner
    st.markdown(
        """
    <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                padding: 1.5rem; border-radius: 12px; color: white; margin-bottom: 1rem;">
        <h4 style="margin: 0 0 0.5rem 0; color: white;">Instant Damage Assessment</h4>
        <p style="margin: 0; opacity: 0.9;">Upload photos of your vehicle damage and get instant 
        repair cost estimates. Speed up your claim from days to minutes!</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Two columns: upload area and instructions
    col_upload, col_info = st.columns([1, 1])

    with col_upload:
        st.markdown("#### 📤 Upload Damage Photos")
        uploaded_files = st.file_uploader(
            "Select images of the vehicle damage",
            type=["jpg", "jpeg", "png", "gif", "webp"],
            accept_multiple_files=True,
            key="damage_uploader",
            help="Upload clear photos of all damaged areas",
        )

        if uploaded_files:
            st.session_state.damage_images = uploaded_files
            st.success(f"✅ {len(uploaded_files)} image(s) ready for analysis")

            # Show thumbnails
            img_cols = st.columns(min(len(uploaded_files), 3))
            for idx, img in enumerate(uploaded_files):
                with img_cols[idx % 3]:
                    st.image(img, caption=f"Image {idx + 1}", width="stretch")

        if st.session_state.damage_images and st.button("🗑️ Clear Images", key="clear_damage"):
            st.session_state.damage_images = []
            st.rerun()

    with col_info:
        st.markdown("#### 📋 How it works")
        st.markdown("""
        1. **Take clear photos** of all damaged areas
        2. **Upload multiple angles** for accuracy
        3. **Ask questions** about the damage
        4. **Get instant estimates** for repairs
        """)

        st.markdown("#### 💡 Tips for best results")
        st.markdown("""
        - Use good lighting
        - Capture close-ups and wide shots
        - Include all damaged areas
        - Show any scratches, dents, or cracks
        """)

    st.markdown("---")

    # Example prompts for damage assessment
    st.markdown("#### Quick actions:")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💰 Estimate repair cost", key="damage_btn1"):
            st.session_state.damage_prompt = (
                "Please analyze the damage and provide a repair cost estimate."
            )
    with col2:
        if st.button("📝 Describe damage", key="damage_btn2"):
            st.session_state.damage_prompt = (
                "Describe all visible damage in detail for my insurance claim."
            )
    with col3:
        if st.button("⚠️ Safety assessment", key="damage_btn3"):
            st.session_state.damage_prompt = (
                "Is this vehicle safe to drive? What are the safety concerns?"
            )

    st.markdown("---")

    # Chat history
    display_chat_history(st.session_state.damage_messages, avatar_assistant="🔧")

    # Chat input
    user_input = st.chat_input(
        "Describe the damage or ask about repair estimates...", key="damage_chat_input"
    )

    if user_input:
        st.session_state.damage_prompt = user_input

    # Process prompt
    if st.session_state.damage_prompt:
        prompt = st.session_state.damage_prompt
        st.session_state.damage_prompt = None
        images = st.session_state.damage_images
        has_images = len(images) > 0

        with st.chat_message("user", avatar="🧑"):
            st.write(prompt)

        st.session_state.damage_messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant", avatar="🔧"):
            message_placeholder = st.empty()
            with st.spinner("Analyzing damage..."):
                if has_images:
                    full_response = process_multimodal_response(
                        f"You are an auto damage assessment expert. {prompt}",
                        st.session_state.damage_messages,
                        images,
                        message_placeholder,
                    )
                    st.session_state.damage_images = []
                else:
                    full_response = process_text_response(
                        f"You are an auto damage assessment expert. {prompt}",
                        st.session_state.damage_messages,
                        message_placeholder,
                    )

        st.session_state.damage_messages.append({"role": "assistant", "content": full_response})
        st.rerun()


# =============================================================================
# TAB 3: Damage Annotation & Documentation
# =============================================================================
def render_image_tools():
    """Render the damage annotation and documentation tools"""
    st.markdown("## ✏️ Damage Annotation & Documentation")

    st.markdown(
        """
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 1.5rem; border-radius: 12px; color: white; margin-bottom: 1rem;">
        <h4 style="margin: 0 0 0.5rem 0; color: white;">Annotate & Document Damage</h4>
        <p style="margin: 0; opacity: 0.9;">Upload accident photos and use AI to circle, highlight, 
        or annotate specific damage areas - marking dents, scratches, or structural issues with 
        arrows and labels for clear documentation.</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Two columns: main content and tips
    col_main, col_tips = st.columns([2, 1])

    with col_tips:
        st.markdown("#### 📋 Annotation Tips")
        st.markdown("""
        **For adjusters:**
        - Mark all visible damage points
        - Use clear labels (dent, scratch, crack)
        - Include severity indicators
        - Note pre-existing vs new damage
        
        **For customers:**
        - Circle the main damage areas
        - Add arrows pointing to scratches
        - Label each damage type
        - Include measurements if possible
        """)

        st.markdown("#### 🏷️ Common Labels")
        st.code("""
• Dent (minor/major)
• Scratch (surface/deep)
• Crack (paint/glass/structural)
• Broken (mirror/light/bumper)
• Misalignment
• Paint damage
• Rust/corrosion
        """)

    with col_main:
        st.markdown("#### 📤 Upload Accident Photo")
        edit_image = st.file_uploader(
            "Select an accident or damage photo to annotate",
            type=["jpg", "jpeg", "png", "gif", "webp"],
            key="tools_edit_uploader",
            help="Upload clear photos of vehicle damage for annotation",
        )

        if edit_image:
            st.image(edit_image, caption="Original Photo", width="stretch")

        # Quick annotation buttons (placed before text area to set default value)
        st.markdown("#### 🖊️ Annotation Instructions")
        st.markdown("**Quick annotations** (click to generate immediately):")
        anno_col1, anno_col2, anno_col3 = st.columns(3)
        with anno_col1:
            if st.button("🔴 Circle damage", key="anno_btn1", disabled=not edit_image):
                st.session_state.annotation_quick_prompt = (
                    "Circle all visible damage areas with red outlines and number each one"
                )
                st.session_state.annotation_process_now = True
                st.rerun()
        with anno_col2:
            if st.button("➡️ Add arrows", key="anno_btn2", disabled=not edit_image):
                st.session_state.annotation_quick_prompt = (
                    "Add arrows pointing to each scratch and dent with descriptive labels"
                )
                st.session_state.annotation_process_now = True
                st.rerun()
        with anno_col3:
            if st.button("📝 Full annotation", key="anno_btn3", disabled=not edit_image):
                st.session_state.annotation_quick_prompt = (
                    "Create a complete damage annotation: circle all damage, "
                    "add arrows with labels describing each issue "
                    "(dent, scratch, crack, etc.), and include severity indicators"
                )
                st.session_state.annotation_process_now = True
                st.rerun()

        st.markdown("**Or describe custom annotations:**")
        # Get value from quick prompt if set (populated by quick buttons)
        default_prompt = st.session_state.get("annotation_quick_prompt", "")

        edit_prompt = st.text_area(
            "Describe what annotations to add",
            value=default_prompt,
            placeholder=(
                "Circle the dent on the front bumper with a red outline, "
                "add an arrow pointing to the scratch on the door with label "
                "'Deep scratch - 12 inches', highlight the cracked headlight..."
            ),
            key="tools_edit_prompt",
            disabled=not edit_image,
            height=100,
        )

        if st.button(
            "✏️ Generate Annotated Image",
            key="tools_edit_btn",
            disabled=not edit_image or not edit_prompt,
            type="primary",
        ):
            st.session_state.annotation_quick_prompt = edit_prompt
            st.session_state.annotation_process_now = True
            st.rerun()

        # Process annotation (triggered by quick buttons or generate button)
        if st.session_state.annotation_process_now and edit_image:
            prompt_to_use = st.session_state.annotation_quick_prompt
            st.session_state.annotation_process_now = False

            if prompt_to_use:
                with st.spinner("Creating annotated documentation..."):
                    try:
                        img_bytes = edit_image.read()
                        edit_image.seek(0)
                        encoded = base64.b64encode(img_bytes).decode("utf-8")

                        response_generator = get_response_generator()
                        result = response_generator.edit_image(
                            image_data=encoded,
                            edit_prompt=f"For insurance damage documentation: {prompt_to_use}",
                        )

                        st.success("✅ Annotated image created!")
                        st.image(result, caption="Annotated Damage Photo", width="stretch")

                        # Clear the quick annotation prompt after use
                        st.session_state.annotation_quick_prompt = ""

                    except Exception as e:
                        error_msg = str(e)
                        st.error(f"❌ Error: {error_msg}")

                        if "doesn't support image editing" in error_msg:
                            st.warning(
                                "**Image annotation is currently experimental.** "
                                "This feature uses AI image generation to create "
                                "annotated versions of your damage photos."
                            )


# =============================================================================
# Main Application
# =============================================================================
def main():
    initialize_session_state()

    # App header
    st.markdown(
        """
    <div style="text-align: center; padding: 1rem 0 1.5rem 0;">
        <h1 style="margin: 0;">🏢 Insurance Portal</h1>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Main tabs
    tab1, tab2, tab3 = st.tabs(
        ["💬 Insurance Assistant", "🚗 Auto Damage Assessment", "✏️ Damage Annotation"]
    )

    with tab1:
        render_text_chatbot()

    with tab2:
        render_damage_assessment()

    with tab3:
        render_image_tools()


if __name__ == "__main__":
    main()
