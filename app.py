import streamlit as st
import requests
import pandas as pd
import fitz
import tempfile
import os
from io import BytesIO


# ======================================================
# PAGE SETTINGS
# ======================================================

st.set_page_config(
    page_title="Publication Keyword Search",
    layout="wide"
)


st.title("📚 Publication Keyword Search")

st.write(
    "Search OpenAlex publications, download Open Access PDFs, "
    "and identify keyword evidence from full text."
)


# ======================================================
# USER INPUT
# ======================================================

authors_text = st.text_area(
    "Authors (one per line)",
    "",
    placeholder="Enter author names, one per line",
    height=120
)


col1, col2 = st.columns(2)


with col1:

    start_year = st.number_input(
        "Start Year",
        value=2025
    )


with col2:

    end_year = st.number_input(
        "End Year",
        value=2026
    )



keywords_text = st.text_area(
    "Keywords (one per line)",
    """Brain and Mind
BMC
Sydney Imaging
University of Sydney MRI
Siemens 3T
3T
3 Tesla
Tesla""",
    height=150
)



authors = [
    x.strip()
    for x in authors_text.splitlines()
    if x.strip()
]


keywords = [
    x.strip()
    for x in keywords_text.splitlines()
    if x.strip()
]



# ======================================================
# FUNCTIONS
# ======================================================


def search_openalex(author):

    url = "https://api.openalex.org/works"


    params = {

        "search": author,

        "filter":
        f"from_publication_date:{start_year}-01-01,"
        f"to_publication_date:{end_year}-12-31,"
        "open_access.is_oa:true",

        "per_page":200

    }


    try:

        response = requests.get(
            url,
            params=params,
            timeout=60
        )


        return response.json().get(
            "results",
            []
        )


    except:

        return []



def download_pdf(url):

    try:

        r=requests.get(
            url,
            timeout=60
        )


        if r.status_code==200:

            return r.content


    except:

        pass


    return None




def extract_text(pdf_bytes):

    try:

        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False
        ) as tmp:

            tmp.write(pdf_bytes)

            filename=tmp.name



        doc=fitz.open(
            filename
        )


        text=""


        for page in doc:

            text += page.get_text()



        doc.close()

        os.remove(filename)


        return text.lower()



    except:

        return ""




def find_keywords(text):

    found=[]


    for k in keywords:

        if k.lower() in text:

            found.append(k)


    return found



# ======================================================
# RUN SEARCH
# ======================================================

if st.button("🔍 Search Publications"):


    if len(authors)==0:

        st.error(
            "Please enter at least one author."
        )

        st.stop()



    results=[]


    status=st.empty()

    progress_bar=st.progress(
        0,
        text="Starting..."
    )


    counter=st.empty()



    # -----------------------------------------------
    # First collect papers
    # -----------------------------------------------

papers_to_check=[]


openalex_progress = st.progress(
    0,
    text="Searching authors..."
)


for i, author in enumerate(authors):


    status.write(
        f"🔎 Searching OpenAlex for: {author}"
    )


    papers = search_openalex(
        author
    )


    for p in papers:

        p["author_search"] = author

        papers_to_check.append(
            p
        )


    openalex_percent = int(
        ((i + 1) / len(authors)) * 100
    )


    openalex_progress.progress(
        (i + 1) / len(authors),
        text=f"OpenAlex search {openalex_percent}%"
    )


openalex_progress.empty()



    total=len(
        papers_to_check
    )



    if total==0:

        st.warning(
            "No papers found."
        )

        st.stop()



    status.write(
        f"Found {total} papers. Downloading PDFs..."
    )



    processed=0



    # -----------------------------------------------
    # PDF processing
    # -----------------------------------------------

    for paper in papers_to_check:


        processed +=1


        title=paper.get(
            "title",
            ""
        )


        year=paper.get(
            "publication_year",
            ""
        )


        author=paper.get(
            "author_search",
            ""
        )


        pdf=None



        if paper.get(
            "best_oa_location"
        ):


            pdf=paper[
                "best_oa_location"
            ].get(
                "pdf_url"
            )



        evidence=[]



        if pdf:


            status.write(
                f"📄 Reading PDF: {title[:100]}"
            )


            pdf_bytes=download_pdf(
                pdf
            )


            if pdf_bytes:


                text=extract_text(
                    pdf_bytes
                )


                evidence=find_keywords(
                    text
                )



        if evidence:


            results.append({

                "Author":author,

                "Year":year,

                "Title":title,

                "Evidence":", ".join(evidence),

                "PDF":pdf

            })



        percent=int(
            processed/total*100
        )


        progress_bar.progress(
    processed / total,
    text=f"PDF processing {percent}%"
        )


        counter.write(
            f"Checked {processed}/{total} papers | "
            f"Matches found: {len(results)}"
        )



    # ==================================================
    # OUTPUT
    # ==================================================


    df=pd.DataFrame(
        results
    )


    if len(df)==0:


        st.warning(
            "No keyword matches found."
        )


    else:


        st.success(
            f"Finished. Found {len(df)} matching papers."
        )


        st.dataframe(
            df,
            use_container_width=True
        )



        output=BytesIO()



        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:


            df.to_excel(
                writer,
                index=False
            )



        st.download_button(

            "📥 Download Excel",

            output.getvalue(),

            "BMC_MRI_publication_search.xlsx",

            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        )
