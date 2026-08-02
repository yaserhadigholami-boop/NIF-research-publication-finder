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
    "and find evidence of selected keywords."
)



# ======================================================
# INPUTS
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
        value=2023,
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
    a.strip()
    for a in authors_text.splitlines()
    if a.strip()
]


keywords = [
    k.strip()
    for k in keywords_text.splitlines()
    if k.strip()
]



# ======================================================
# OPENALEX SEARCH
# ======================================================


def search_openalex(author, status):


    # ---------------------------------------------
    # METHOD 1
    # Original approach
    # ---------------------------------------------

    status.write(
        f"🔎 Searching OpenAlex works for {author}"
    )


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

        r = requests.get(
            url,
            params=params,
            timeout=60
        )


        papers = r.json().get(
            "results",
            []
        )


        if len(papers) > 0:

            status.write(
                f"✅ Found {len(papers)} papers using normal search"
            )

            return papers


    except:

        pass



    # ---------------------------------------------
    # METHOD 2
    # Author ID fallback
    # ---------------------------------------------

    status.write(
        "⚠️ No papers found. Trying author profile search..."
    )



    author_url = (
        "https://api.openalex.org/authors"
    )


    author_params = {

        "search": author,

        "per_page":5

    }



    try:

        r = requests.get(
            author_url,
            params=author_params,
            timeout=60
        )


        author_results = r.json().get(
            "results",
            []
        )


        if len(author_results)==0:

            return []



        author_id = (
            author_results[0]["id"]
            .split("/")[-1]
        )



        status.write(
            f"👤 Found author profile. Searching publications..."
        )



        works_url = (
            "https://api.openalex.org/works"
        )


        works_params = {


            "filter":
            f"author.id:{author_id},"
            f"from_publication_date:{start_year}-01-01,"
            f"to_publication_date:{end_year}-12-31,"
            "open_access.is_oa:true",


            "per_page":200

        }



        r = requests.get(
            works_url,
            params=works_params,
            timeout=60
        )


        papers = r.json().get(
            "results",
            []
        )



        status.write(
            f"✅ Found {len(papers)} papers using author profile"
        )


        return papers



    except:

        return []



# ======================================================
# PDF FUNCTIONS
# ======================================================


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


        text=""


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



# ======================================================
# RUN APP
# ======================================================


if st.button("🔍 Search Publications"):


    if len(authors)==0:

        st.error(
            "Please enter an author."
        )

        st.stop()



    status = st.empty()

    message = st.empty()

    progress_text = st.empty()



    all_papers=[]



    # ---------------------------------------------
    # SEARCH STAGE
    # ---------------------------------------------

    search_bar = st.progress(
        0,
        text="Searching OpenAlex..."
    )


    for i, author in enumerate(authors):


        papers = search_openalex(
            author,
            status
        )



        for p in papers:

            p["author_name"]=author

            all_papers.append(
                p
            )



        progress = (
            i+1
        )/len(authors)


        search_bar.progress(
            progress,
            text=f"Search {int(progress*100)}%"
        )



    search_bar.empty()



    total=len(
        all_papers
    )



    if total==0:

        st.warning(
            "No papers found."
        )

        st.stop()



    status.write(
        f"📚 Found {total} papers. Starting PDF analysis..."
    )


    message.write(
        "⬇️ Downloading PDFs and searching text..."
    )



    # ---------------------------------------------
    # PDF STAGE
    # ---------------------------------------------


    pdf_bar = st.progress(
        0,
        text="Processing PDFs..."
    )


    results=[]


    processed=0



    for paper in all_papers:


        processed += 1


        title = paper.get(
            "title",
            ""
        )


        year = paper.get(
            "publication_year",
            ""
        )


        author = paper.get(
            "author_name",
            ""
        )



        pdf=None



        if paper.get(
            "best_oa_location"
        ):


            pdf = paper[
                "best_oa_location"
            ].get(
                "pdf_url"
            )



        if pdf:


            message.write(
                f"📄 Reading PDF: {title[:100]}"
            )


            pdf_bytes = download_pdf(
                pdf
            )


            if pdf_bytes:


                text = extract_text(
                    pdf_bytes
                )


                evidence = find_keywords(
                    text
                )


                if len(evidence)>0:


                    results.append({

                        "Author":author,

                        "Year":year,

                        "Title":title,

                        "Evidence":
                        ", ".join(evidence),

                        "PDF":pdf

                    })



        progress = processed/total


        pdf_bar.progress(
            progress,
            text=f"PDF analysis {int(progress*100)}%"
        )


        progress_text.write(
            f"Processed {processed}/{total} | "
            f"Matches found: {len(results)}"
        )



    # ---------------------------------------------
    # OUTPUT
    # ---------------------------------------------


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
                index=False,
                sheet_name="Results"
            )



        st.download_button(

            "📥 Download Excel",

            output.getvalue(),

            "Publication_Search.xlsx",

            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        )
