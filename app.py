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



    results = []


    progress_bar = st.progress(0)


    status = st.empty()


    counter = st.empty()



    # ---------------------------------------------
    # GET ALL PAPERS FIRST
    # ---------------------------------------------

    status.write(
        "Collecting publications from OpenAlex..."
    )


    author_papers = {}


    total_papers = 0



    for author in authors:


        papers = search_openalex(author)


        author_papers[author] = papers


        total_papers += len(papers)



    if total_papers == 0:

        st.warning(
            "No publications found."
        )

        st.stop()



    status.write(
        f"Found {total_papers} publications. Checking PDFs..."
    )



    processed = 0



    # ---------------------------------------------
    # CHECK PAPERS
    # ---------------------------------------------

    for author in authors:


        papers = author_papers[author]



        for paper in papers:


            processed += 1



            title = paper.get(
                "title",
                ""
            )


            year = paper.get(
                "publication_year",
                ""
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


                pdf_bytes = download_pdf(pdf)



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

                            "Evidence": ", ".join(evidence),

                            "PDF": pdf

                        })



            # UPDATE PROGRESS

            progress = processed / total_papers


            progress_bar.progress(
                progress
            )


            counter.write(
                f"Processed {processed}/{total_papers} papers | "
                f"Matches found: {len(results)}"
            )



    # ---------------------------------------------
    # OUTPUT
    # ---------------------------------------------

    df = pd.DataFrame(results)



    if len(df) == 0:

        st.warning(
            "No matching publications found."
        )


    else:

        st.success(
            f"Completed! Found {len(df)} matching papers."
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
                index=False
            )



        st.download_button(

            label="📥 Download Excel",

            data=output.getvalue(),

            file_name="Publication_Search.xlsx",

            mime=
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        )
