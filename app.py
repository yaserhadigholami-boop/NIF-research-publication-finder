import streamlit as st
import requests
import pandas as pd
import fitz
import tempfile
import os
from io import BytesIO


# --------------------------------------------------------
# PAGE SETTINGS
# --------------------------------------------------------

st.set_page_config(
    page_title="Publication Keyword Search",
    layout="wide"
)


st.title("📚 Publication Keyword Search")

st.write(
    "Search OpenAlex publications, download Open Access PDFs, "
    "and find evidence of selected keywords."
)


# --------------------------------------------------------
# USER INPUTS
# --------------------------------------------------------

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
        value=2019,
        step=1
    )


with col2:

    end_year = st.number_input(
        "End Year",
        value=2026,
        step=1
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


if len(authors) == 0:

    st.info(
        "Enter author names to start searching."
    )


# --------------------------------------------------------
# OPENALEX AUTHOR SEARCH
# --------------------------------------------------------

def get_author_id(author_name):

    url = "https://api.openalex.org/authors"


    params = {

        "search": author_name,

        "per_page": 5

    }


    try:

        r = requests.get(
            url,
            params=params,
            timeout=30
        )

        data = r.json()


        results = data.get(
            "results",
            []
        )


        if len(results) > 0:

            return results[0]["id"]


    except:

        pass


    return None



# --------------------------------------------------------
# SEARCH AUTHOR PAPERS
# --------------------------------------------------------

def search_author_papers(author_id):

    url = "https://api.openalex.org/works"


    params = {

        "filter":
        f"author.id:{author_id},"
        f"from_publication_date:{start_year}-01-01,"
        f"to_publication_date:{end_year}-12-31,"
        "open_access.is_oa:true",

        "per_page":200

    }


    try:

        r = requests.get(
            url,
            params=params,
            timeout=60
        )

        return r.json().get(
            "results",
            []
        )


    except:

        return []



# --------------------------------------------------------
# PDF FUNCTIONS
# --------------------------------------------------------

def download_pdf(url):

    try:

        r = requests.get(
            url,
            timeout=60
        )


        if r.status_code == 200:

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

            filename = tmp.name



        doc = fitz.open(
            filename
        )


        text = ""


        for page in doc:

            text += page.get_text()



        doc.close()


        os.remove(
            filename
        )


        return text.lower()



    except:

        return ""



def find_keywords(text):

    found=[]


    for k in keywords:

        if k.lower() in text:

            found.append(k)


    return found



# --------------------------------------------------------
# RUN SEARCH
# --------------------------------------------------------

if st.button("🔍 Search Publications"):


    if len(authors)==0:

        st.error(
            "Please enter an author name."
        )

        st.stop()



    all_results=[]

    match_results=[]



    # ------------------------------
    # AUTHOR SEARCH PROGRESS
    # ------------------------------

    status = st.empty()

    progress = st.progress(
        0,
        text="Starting..."
    )



    author_ids=[]



    for i, author in enumerate(authors):


        status.write(
            f"🔎 Finding author: {author}"
        )


        author_id = get_author_id(
            author
        )


        if author_id:

            author_ids.append(
                (
                    author,
                    author_id
                )
            )


        progress.progress(
            (i+1)/len(authors),
            text=
            f"Author search {int((i+1)/len(authors)*100)}%"
        )



    if len(author_ids)==0:

        st.error(
            "No OpenAlex authors found."
        )

        st.stop()



    # ------------------------------
    # PAPER COLLECTION
    # ------------------------------

    status.write(
        "📚 Collecting publications..."
    )


    papers=[]


    for author, author_id in author_ids:


        author_papers = search_author_papers(
            author_id
        )


        for p in author_papers:

            p["search_author"]=author

            papers.append(p)



    total=len(papers)



    if total==0:

        st.warning(
            "No publications found."
        )

        st.stop()



    status.write(
        f"Found {total} papers. Checking PDFs..."
    )



    # ------------------------------
    # PDF PROGRESS
    # ------------------------------

    processed=0


    progress_bar=st.progress(
        0,
        text="Checking papers..."
    )


    counter=st.empty()



    for paper in papers:


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
            "search_author",
            ""
        )


        status.write(
            f"📄 Checking: {title[:100]}"
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



        result={

            "Author":author,

            "Year":year,

            "Title":title,

            "Keyword Match":
            "Yes" if evidence else "No",

            "Evidence Found":
            ", ".join(evidence),

            "PDF":pdf

        }


        all_results.append(
            result
        )


        if evidence:

            match_results.append(
                result
            )



        percent=int(
            processed/total*100
        )


        progress_bar.progress(
            processed/total,
            text=f"Processing {percent}%"
        )


        counter.write(
            f"{processed}/{total} papers checked | "
            f"{len(match_results)} matches found"
        )



    # ------------------------------
    # OUTPUT
    # ------------------------------

    all_df=pd.DataFrame(
        all_results
    )


    match_df=pd.DataFrame(
        match_results
    )


    st.success(
        f"Completed. Found {len(match_df)} matching papers."
    )


    st.subheader(
        "All Publications Checked"
    )


    st.dataframe(
        all_df,
        use_container_width=True
    )


    st.subheader(
        "Keyword Matches"
    )


    st.dataframe(
        match_df,
        use_container_width=True
    )



    # Excel

    output=BytesIO()


    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:


        all_df.to_excel(
            writer,
            sheet_name="All Publications",
            index=False
        )


        match_df.to_excel(
            writer,
            sheet_name="Keyword Matches",
            index=False
        )



    st.download_button(

        "📥 Download Excel Report",

        output.getvalue(),

        "Publication_Search_Report.xlsx",

        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    )
