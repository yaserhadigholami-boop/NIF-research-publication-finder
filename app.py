import streamlit as st
import pandas as pd
import requests
import re
import difflib
import io
import os
import time

from bs4 import BeautifulSoup
import fitz


# ======================================================
# STREAMLIT SETTINGS
# ======================================================

st.set_page_config(
    page_title="Publication Finder",
    layout="wide"
)


st.title("📚 Publication Finder v2.0")
st.write(
    "Search publications by author, year range and keywords"
)



# ======================================================
# USER INPUT
# ======================================================


with st.sidebar:


    st.header("Search Settings")


   AUTHOR_NAME = st.text_input(
        "Author name",
        placeholder="Enter author full name"
    )


    ORCID = st.text_input(
        "ORCID (optional)",
        ""
    )


    INSTITUTION = st.text_input(
        "Institution",
        "University of Sydney"
    )


    COUNTRY = st.text_input(
        "Country",
        "Australia"
    )



    START_YEAR, END_YEAR = st.slider(
        "Publication year range",
        1900,
        2026,
        (2011,2026)
    )



    keyword_text = st.text_area(
        "Keywords (one per line)",
        """
Brain and Mind
BMC
Sydney Imaging
University of Sydney MRI
Siemens 3T
3T
3 Tesla
MRI
PET-MR
PET MRI
nanoparticle
radiolabel
"""
    )


    KEYWORDS = [

        x.strip()

        for x in keyword_text.split("\n")

        if x.strip()

    ]



    run_button = st.button(
        "🔍 Search Publications"
    )



# ======================================================
# FUNCTIONS
# ======================================================


def clean_name(name):

    name=name.lower()

    name=re.sub(
        r"[^a-z ]",
        "",
        name
    )

    return name.strip()



def name_score(target,candidate):

    return int(

        difflib.SequenceMatcher(

            None,

            clean_name(target),

            clean_name(candidate)

        ).ratio()*100

    )




def search_openalex_authors(name):

    url="https://api.openalex.org/authors"


    params={

        "search":name,

        "per_page":25

    }


    r=requests.get(

        url,

        params=params,

        timeout=60

    )


    return r.json().get(
        "results",
        []
    )




def score_author(author):


    score=0


    name=author.get(
        "display_name",
        ""
    )


    score += name_score(
        AUTHOR_NAME,
        name
    )


    if ORCID:


        if author.get("orcid"):


            if ORCID.lower() in author["orcid"].lower():

                score +=100



    institutions=[]


    for inst in author.get(
        "last_known_institutions",
        []
    ):


        institutions.append(

            inst.get(
                "display_name",
                ""
            ).lower()

        )


    text=" ".join(institutions)



    if INSTITUTION.lower() in text:

        score+=40



    if "sydney" in text:

        score+=20



    return score





def find_best_author(progress,status):


    status.info(
        "Searching OpenAlex author profiles..."
    )


    candidates=search_openalex_authors(
        AUTHOR_NAME
    )


    if len(candidates)==0:

        return None



    ranked=[]


    for i,a in enumerate(candidates):


        ranked.append(

            (
                score_author(a),
                a
            )

        )


        progress.progress(
            int((i+1)/len(candidates)*20)
        )


    ranked.sort(
        key=lambda x:x[0],
        reverse=True
    )


    return ranked[0][1]






def get_openalex_works(author_id,progress,status):


    status.info(
        "Searching OpenAlex publications..."
    )


    author_id=author_id.replace(
        "https://openalex.org/",
        ""
    )


    url="https://api.openalex.org/works"


    params={

        "filter":

        f"author.id:{author_id},"
        f"from_publication_date:{START_YEAR}-01-01,"
        f"to_publication_date:{END_YEAR}-12-31",


        "per_page":200,

        "sort":
        "publication_date:desc"

    }



    r=requests.get(
        url,
        params=params
    )


    return r.json().get(
        "results",
        []
    )







def get_crossref_works():

    status="Searching Crossref"


    url="https://api.crossref.org/works"


    params={


        "query.author":
        AUTHOR_NAME,


        "rows":
        100,


        "filter":

        f"from-pub-date:{START_YEAR}-01-01,"
        f"until-pub-date:{END_YEAR}-12-31"

    }


    try:

        r=requests.get(
            url,
            params=params,
            timeout=60
        )


        return r.json()["message"]["items"]


    except:

        return []







def extract_openalex_abstract(work):


    inv=work.get(
        "abstract_inverted_index"
    )


    if not inv:

        return ""


    words=[]


    for word,pos in inv.items():

        for p in pos:

            words.append(
                (
                    p,
                    word
                )
            )


    words.sort()


    return " ".join(

        [
            x[1]
            for x in words
        ]

    )






def keyword_search(text):


    found=[]


    evidence=[]


    text=text.lower()


    sentences=re.split(
        r"[.!?]",
        text
    )



    for k in KEYWORDS:


        if k.lower() in text:


            found.append(k)


            for s in sentences:


                if k.lower() in s:

                    evidence.append(
                        s.strip()
                    )

                    break



    return found,evidence






def analyse_papers(papers,progress,status):


    results=[]


    total=len(papers)



    for i,paper in enumerate(papers):


        status.info(

            f"Analysing paper {i+1}/{total}"

        )


        text=extract_openalex_abstract(
            paper
        )



        keywords,evidence=keyword_search(
            text
        )



        if keywords:


            results.append({

                "Year":
                paper.get(
                    "publication_year"
                ),


                "Title":
                paper.get(
                    "title"
                ),


                "Keywords":
                ", ".join(keywords),


                "Evidence":
                " | ".join(evidence),


                "DOI":
                paper.get(
                    "doi",
                    ""
                )

            })


        progress.progress(

            20 + int((i+1)/total*80)

        )



    return pd.DataFrame(results)






# ======================================================
# MAIN PIPELINE
# ======================================================


if run_button:


    progress=st.progress(0)

    status=st.empty()


    author=find_best_author(
        progress,
        status
    )


    if author is None:

        st.error(
            "Author not found"
        )

        st.stop()



    st.success(
        f"Selected author: {author['display_name']}"
    )



    papers=get_openalex_works(

        author["id"],

        progress,

        status

    )



    st.info(
        f"Found {len(papers)} publications"
    )



    df=analyse_papers(

        papers,

        progress,

        status

    )


    progress.progress(100)


    status.success(
        "Completed"
    )



    st.subheader(
        "Results"
    )


    st.dataframe(
        df,
        use_container_width=True
    )



    if len(df)>0:


        csv=df.to_csv(
            index=False
        )


        st.download_button(

            "Download CSV",

            csv,

            "publication_results.csv",

            "text/csv"

        )


        excel_buffer=io.BytesIO()


        df.to_excel(

            excel_buffer,

            index=False

        )


        st.download_button(

            "Download Excel",

            excel_buffer.getvalue(),

            "publication_results.xlsx"

        )

