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
        value=2011,
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



# ======================================================
# AUTHOR SEARCH
# ======================================================


def find_best_author(author_name, status):


    url = "https://api.openalex.org/authors"


    params = {

        "search": author_name,

        "per_page":10

    }


    try:

        r = requests.get(
            url,
            params=params,
            timeout=60
        )


        results = r.json().get(
            "results",
            []
        )


    except:

        return None



    if len(results)==0:

        return None



    # --------------------------------------
    # Score author profiles
    # --------------------------------------

    scored=[]


    for author in results:


        score=0


        name = author.get(
            "display_name",
            ""
        )


        works = author.get(
            "works_count",
            0
        )


        # affiliations

        institutions = author.get(
            "last_known_institutions",
            []
        )


        inst_text=""


        for inst in institutions:

            inst_text += (
                inst.get("display_name","")
                .lower()
            )



        if "sydney" in inst_text:

            score += 100


        if "australia" in str(
            author
        ).lower():

            score += 50


        score += min(
            works,
            50
        )



        scored.append(
            (
                score,
                author
            )
        )



    scored.sort(
        reverse=True,
        key=lambda x:x[0]
    )



    best = scored[0][1]



    status.write(
        f"👤 Selected OpenAlex profile: "
        f"{best.get('display_name','')}"
    )


    status.write(
        f"📚 Publications indexed: "
        f"{best.get('works_count',0)}"
    )


    return best["id"].split("/")[-1]



# ======================================================
# GET AUTHOR PAPERS
# ======================================================


def search_author_papers(author_id):


    url="https://api.openalex.org/works"


    params={


        "filter":
        f"author.id:{author_id},"
        f"from_publication_date:{start_year}-01-01,"
        f"to_publication_date:{end_year}-12-31,"
        "open_access.is_oa:true",


        "per_page":200

    }


    try:

        r=requests.get(
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



# ======================================================
# PDF FUNCTIONS
# ======================================================


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
# RUN
# ======================================================


if st.button("🔍 Search Publications"):


    if len(authors)==0:

        st.error(
            "Enter an author name."
        )

        st.stop()



    status=st.empty()

    message=st.empty()

    progress_text=st.empty()



    all_papers=[]



    # --------------------------------------
    # AUTHOR SEARCH
    # --------------------------------------

    for author in authors:


        status.write(
            f"🔎 Finding author profile: {author}"
        )


        author_id=find_best_author(
            author,
            status
        )


        if author_id is None:

            st.warning(
                f"No author profile found for {author}"
            )

            continue



        message.write(
            "📚 Retrieving publications..."
        )


        papers=search_author_papers(
            author_id
        )


        status.write(
            f"Found {len(papers)} publications"
        )


        for p in papers:

            p["author_name"]=author

            all_papers.append(
                p
            )



    total=len(
        all_papers
    )



    if total==0:

        st.error(
            "No publications found."
        )

        st.stop()



    # --------------------------------------
    # PDF SEARCH
    # --------------------------------------

    status.write(
        f"📄 Analysing {total} papers..."
    )


    pdf_bar=st.progress(
        0
    )


    results=[]


    for i,paper in enumerate(all_papers):


        title=paper.get(
            "title",
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



                if len(evidence)>0:


                    results.append({

                        "Author":
                        paper["author_name"],

                        "Year":
                        paper.get(
                            "publication_year",
                            ""
                        ),

                        "Title":
                        title,

                        "Evidence":
                        ", ".join(evidence),

                        "PDF":
                        pdf

                    })



        percent=(i+1)/total


        pdf_bar.progress(
            percent
        )


        progress_text.write(
            f"Processed {i+1}/{total} | "
            f"Matches: {len(results)}"
        )



    # --------------------------------------
    # OUTPUT
    # --------------------------------------

    df=pd.DataFrame(
        results
    )


    if len(df)==0:

        st.warning(
            "No keyword matches found."
        )

    else:

        st.success(
            f"Found {len(df)} matching papers."
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

            "Publication_Search.xlsx",

            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        )
