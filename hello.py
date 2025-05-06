import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

# --- Firebase Init ---
if not firebase_admin._apps:
    cred = credentials.Certificate("latex.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Helpers ---
def extract_dollar_sections(text):
    dollar_sections = re.findall(r'(\$.*?\$)', text)
    modified = text
    latex_map = {}
    for i, section in enumerate(dollar_sections, 1):
        placeholder = f"F{i}"
        modified = modified.replace(section, placeholder, 1)
        latex_map[placeholder] = section[1:-1]
    return latex_map, modified

def replace_placeholders(modified, latex_map):
    for key, val in latex_map.items():
        modified = modified.replace(key, f"${val}$")
    return modified

# --- UI ---
st.title("📘 LaTeX Question Editor")

question_input = st.text_input("Question", key="Question")
latex_map, modified_text = extract_dollar_sections(question_input)

st.write(modified_text)

# LaTeX editing section
edited_latex_map = {}
for ph in latex_map:
    val = st.text_input(f"{ph}:", value=latex_map[ph], key=f"latex_{ph}")
    edited_latex_map[ph] = val
    st.latex(val)

# Answer Options
col1, col2, col3, col4 = st.columns(4)
answer_inputs = {}
for col, label in zip([col1, col2, col3, col4], ["A", "B", "C", "D"]):
    with col:
        val = st.text_input(label, key=f"ans_{label}")
        answer_inputs[label] = val
        exps = re.findall(r'\$(.*?)\$', val)
        if exps:
            for e in exps:
                st.latex(e)
        else:
            st.write(val)

# Final reconstructed question
final_q = replace_placeholders(modified_text, edited_latex_map)
st.write(final_q)
st.latex(final_q)
st.write("")

# --- Delete from Firestore ---
def delete_from_firestore(doc_id):
    try:
        db.collection("questions").document(doc_id).delete()
        st.success(f"✅ Deleted question with ID: {doc_id}")
    except Exception as e:
        st.error(f"❌ Failed to delete question: {e}")

# --- Handlers ---
@firestore.transactional
def add_with_auto_id(transaction, question, answers):
    counter_ref = db.collection("counters").document("questions")
    counter_doc = counter_ref.get(transaction=transaction)
    current_id = counter_doc.get("current") if counter_doc.exists else 0
    new_id = current_id + 1
    transaction.set(counter_ref, {"current": new_id})
    q_ref = db.collection("questions").document(str(new_id))
    transaction.set(q_ref, {
        "id": new_id,
        "Question": question,
        "A": answers["A"],
        "B": answers["B"],
        "C": answers["C"],
        "D": answers["D"],
    })
    return new_id

# --- Buttons ---
colA, colB = st.columns(2)
with colA:
    submitted = st.button("📤 Send to Firebase")
with colB:
    st.button("🔄 Reset Form", on_click=lambda: st.session_state.update({"clear_form_flag": True}))

# --- Submission logic ---
if submitted:
    if not final_q.strip():
        st.warning("⚠️ Question cannot be empty.")
    elif any(not answer.strip() for answer in answer_inputs.values()):
        st.warning("⚠️ All answers (A, B, C, D) must be filled out.")
    else:
        try:
            transaction = db.transaction()
            new_id = add_with_auto_id(transaction, final_q, answer_inputs)
            st.session_state["clear_form_flag"] = True  # Will trigger clear on next run
            st.success(f"✅ Question saved with ID: {new_id}")
        except Exception as e:
            st.error(f"❌ Failed to send question: {e}")

# --- View All Questions ---
st.subheader("📋 All Questions in Firestore")
try:
    docs = db.collection("questions").stream()
    rows = [{"ID": doc.id, **doc.to_dict()} for doc in docs]
    
    if rows:
        # Create a DataFrame
        df = pd.DataFrame(rows)

        # Add a "Delete" column with buttons to delete the rows
        delete_buttons = []
        for idx, row in df.iterrows():
            delete_buttons.append(
                st.button(f"Delete {row['ID']}", key=f"delete_{row['ID']}", on_click=delete_from_firestore, args=(row['ID'],))
            )

        # Display the table
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

    else:
        st.info("No questions found in Firestore.")
except Exception as e:
    st.error(f"Failed to load questions: {e}")
