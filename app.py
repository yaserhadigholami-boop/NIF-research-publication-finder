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



if len(authors) == 0:

    st.info(
        "Enter author names to start searching."
    )



# --------------------------------------------------------
# FUNCTIONS
# --------------------------------------------------------

def search_openalex(author):

    url = "https://api.openalex.org/works"


    params = {

        "search": author,

        "filter":
        f"from_publication_date:{start_year}-01-01,"
        f"to_publication_date:{end_year}-12-31,"
        "open_access.is_oa:true",

        "per_page": 200

    }


    try:

        response = requests.get(
            url,
            params=params,
            timeout=60
        )

        response.raise_for_status()

        return response.json().get(
            "results",
            []
        )


    except:

        return []



def download_pdf(url):

    try:

        response = requests.get(
            url,
            timeout=60
        )


        if response.status_code == 200:

            return response.content


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



        doc = fitz.open(filename)


        text = ""


        for page in doc:

            text += page.get_text()



        doc.close()


        os.remove(filename)


        return text.lower()



    except:

        return ""



def find_keywords(text):

    found = []


    for keyword in keywords:

        if keyword.lower() in text:

            found.append(keyword)



    return found

# --------------------------------------------------------
# SEARCH BUTTON
# --------------------------------------------------------

if st.button("🔍 Search Publications"):


    if len(authors) == 0:

        st.error(
            "Please enter at least one author name."
        )

        st.stop()



    all_results = []

    matched_results = []



    # Progress elements

    progress_bar = st.progress(
        0,
        text="Starting search..."
    )

    status = st.empty()

    counter = st.empty()



    # ----------------------------------------------------
    # GET PUBLICATIONS
    # ----------------------------------------------------

    status.write(
        "🔎 Searching OpenAlex database..."
    )


    author_papers = {}

    total_papers = 0



    for author in authors:


        papers = search_openalex(author)


        author_papers[author] = papers


        total_papers += len(papers)



    if total_papers == 0:

        st.warning(
            "No publications found for the selected authors and years."
        )

        st.stop()



    status.write(
        f"Found {total_papers} Open Access papers. Checking PDFs..."
    )



    processed = 0



    # ----------------------------------------------------
    # PROCESS PAPERS
    # ----------------------------------------------------

    for author in authors:


        papers = author_papers[author]


        for paper in papers:



            processed += 1


            progress = processed / total_papers

            percentage = int(progress * 100)



            # Update progress BEFORE processing

            progress_bar.progress(
                progress,
                text=f"Processing papers... {percentage}%"
            )



            title = paper.get(
                "title",
                ""
            )


            year = paper.get(
                "publication_year",
                ""
            )



            status.write(
                f"📄 Checking: {title[:120]}"
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



            evidence = []



            # Download PDF and search

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



            # Save ALL papers checked

            result = {

                "Author": author,

                "Year": year,

                "Title": title,

                "Keyword Match":
                    "Yes" if evidence else "No",

                "Evidence Found":
                    ", ".join(evidence),

                "PDF":
                    pdf

            }



            all_results.append(
                result
            )



            if evidence:

                matched_results.append(
                    result
                )



            counter.write(
                f"Progress: {percentage}% | "
                f"Processed {processed}/{total_papers} papers | "
                f"Matches found: {len(matched_results)}"
            )




    # ----------------------------------------------------
    # RESULTS
    # ----------------------------------------------------


    progress_bar.progress(
        1.0,
        text="Completed 100%"
    )


    status.success(
        "✅ Search completed!"
    )



    all_df = pd.DataFrame(
        all_results
    )


    match_df = pd.DataFrame(
        matched_results
    )



    st.subheader(
        "📊 All Checked Publications"
    )


    st.dataframe(
        all_df,
        use_container_width=True
    )



    st.subheader(
        "🎯 Matching Publications"
    )


    if len(match_df) > 0:

        st.dataframe(
            match_df,
            use_container_width=True
        )

    else:

        st.info(
            "No keyword matches found."
        )



    # ----------------------------------------------------
    # EXCEL DOWNLOADS
    # ----------------------------------------------------


    excel_all = BytesIO()


    with pd.ExcelWriter(
        excel_all,
        engine="openpyxl"
    ) as writer:


        all_df.to_excel(
            writer,
            index=False,
            sheet_name="All Publications"
        )


        match_df.to_excel(
            writer,
            index=False,
            sheet_name="Keyword Matches"
        )



    st.download_button(

        label="📥 Download Complete Excel Report",

        data=excel_all.getvalue(),

        file_name=
        "Publication_Keyword_Search_Report.xlsx",

        mime=
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    )
