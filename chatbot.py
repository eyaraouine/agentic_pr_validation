import streamlit as st
import openai

# --- Configuration de la page ---
st.set_page_config(page_title="Chat GPT-4", page_icon="🧠")

# --- Clé API ---
api_key = st.sidebar.text_input("🔑 Entrez votre clé API OpenAI", type="password")

# --- Choix du modèle ---
model = st.sidebar.selectbox("Modèle", ["gpt-4", "gpt-3.5-turbo"])

# --- Initialisation de l'historique ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "Tu es un assistant utile."}
    ]

# --- Affichage de l'historique ---
for msg in st.session_state.messages[1:]:  # On saute le "system"
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Saisie utilisateur ---
if prompt := st.chat_input("Écris ton message ici..."):
    # Ajoute le message utilisateur à l'historique
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Affiche un message d'attente
    with st.chat_message("assistant"):
        with st.spinner("GPT réfléchit..."):
            try:
                openai.api_key = api_key
                response = openai.ChatCompletion.create(
                    model=model,
                    messages=st.session_state.messages
                )
                reply = response.choices[0].message.content
            except Exception as e:
                reply = f"❌ Erreur : {e}"

            st.markdown(reply)

    # Ajoute la réponse de l'assistant à l'historique
    st.session_state.messages.append({"role": "assistant", "content": reply})
