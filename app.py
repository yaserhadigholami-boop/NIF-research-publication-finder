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
# USER INPUTS
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
        value=2025,
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
# FUNCTIONS
# ======================================================


def search_openalex(author):

    # ---------------------------------------
    # Method 1: Original working approach
    # ---------------------------------------

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

        papers = response.json().get(
            "results",
            []
        )


        if len(papers) > 0:

            return papers


    except:

        pass



    # ---------------------------------------
    # Method 2: Author ID fallback
    # ---------------------------------------

    author_url = "https://api.openalex.org/authors"


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


        authors_found = r.json().get(
            "results",
            []
        )


        if len(authors_found)==0:

            return []



        author_id = authors_found[0]["id"].split("/")[-1]



        works_url = "https://api.openalex.org/works"


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


        return r.json().get(
            "results",
            []
        )


    except:

        return []



# ======================================================
# MAIN SEARCH
# ======================================================


if st.button("🔍 Search Publications"):


    if len(authors) == 0:

        st.error(
            "Please enter at least one author name."
        )

        st.stop()



    results = []


    # Status containers

    status = st.empty()

    message = st.empty()

    progress_text = st.empty()



    # ==================================================
    # STAGE 1: OPENALEX SEARCH
    # ==================================================

    status.write(
        "🔎 Starting OpenAlex search..."
    )


    openalex_bar = st.progress(
        0,
        text="Searching database..."
    )


    all_papers = []



    for index, author in enumerate(authors):


        status.write(
            f"🔎 Searching OpenAlex for: **{author}**"
        )


        message.write(
            "⏳ Waiting for OpenAlex response..."
        )


        papers = search_openalex(
            author
        )


        message.write(
            f"📚 Retrieved {len(papers)} publications for {author}"
        )



        for paper in papers:

            paper["author_name"] = author

            all_papers.append(
                paper
            )



        search_progress = (
            index + 1
        ) / len(authors)


        openalex_bar.progress(
            search_progress,
            text=
            f"OpenAlex search {int(search_progress*100)}%"
        )



    openalex_bar.empty()



    total = len(
        all_papers
    )



    if total == 0:

        st.warning(
            "No Open Access publications found."
        )

        st.stop()



    # ==================================================
    # STAGE 2: PDF ANALYSIS
    # ==================================================

    status.write(
        f"📚 Found {total} papers. Starting PDF analysis..."
    )


    message.write(
        "⬇️ Downloading PDFs and searching full text..."
    )


    pdf_bar = st.progress(
        0,
        text="Processing PDFs..."
    )



    processed = 0



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



        status.write(
            f"📄 Reading: {title[:120]}"
        )



        pdf = None



        if paper.get(
            "best_oa_location"
        ):


            pdf = paper[
                "best_oa_location"
            ].get(
                "pdf_url"
            )



        if pdf:


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



                if len(evidence) > 0:


                    results.append({

                        "Author": author,

                        "Year": year,

                        "Title": title,

                        "Evidence":
                        ", ".join(evidence),

                        "PDF": pdf

                    })



        percent = processed / total



        pdf_bar.progress(
            percent,
            text=
            f"PDF processing {int(percent*100)}%"
        )



        progress_text.write(
            f"Processed {processed}/{total} papers | "
            f"Keyword matches found: {len(results)}"
        )



    # ==================================================
    # RESULTS
    # ==================================================


    df = pd.DataFrame(
        results
    )



    if len(df) == 0:


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



        output = BytesIO()



        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:


            df.to_excel(
                writer,
                index=False,
                sheet_name="Keyword Matches"
            )



        st.download_button(

            label="📥 Download Excel Report",

            data=output.getvalue(),

            file_name=
            "BMC_MRI_publication_search.xlsx",

            mime=
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        )
