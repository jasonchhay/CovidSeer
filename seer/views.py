from django.http import Http404, HttpResponse
from django.shortcuts import render
from django import template
from . import models
from elasticsearch import Elasticsearch

from rest_framework.decorators import api_view
from rest_framework.response import Response

import json
import os

ERR_QUERY_NOT_FOUND = '<h1>Query not found</h1>'
ERR_IMG_NOT_AVAILABLE = 'The requested result can not be shown now'

# USER = open("elastic-settings.txt").read().split("\n")[1]
# PASSWORD = open("elastic-settings.txt").read().split("\n")[2]
ELASTIC_INDEX = 'cord_final'

# open connection to Elastic
es = Elasticsearch(['http://csxindex05:9200/'], verify_certs=True)
register = template.Library()

if not es.ping():
    raise ValueError("Connection failed")

@register.filter
def subtract(value, arg):
    return value - arg

def Home(request):
    return render(request, 'seer/index.html')


# Formats the list of authors with their metadata
def __get_author_list(result):

    author_results = result['_source']['metadata']['authors']
    author_list = []

    if isinstance(author_results, list) and len(author_results) > 0:
        for data in author_results:
            author = dict()

            """
            # Build the name for the author
            first_name = data['first']
            mid_name = data['middle']

            if len(mid_name) > 0:
                first_name += " " + mid_name[0]

            last_name = data['last']
            # suffix = data['suffix']
            suffix =''

            author['name'] = ' '.join([first_name, last_name, suffix])

            if suffix is None or suffix == '':
                author['name'] = ' '.join([first_name, last_name])
                #print(first_name)
            else:
                author['name'] = ' '.join([first_name, last_name, suffix])
                #print("SUFFIX:", suffix)
            """

            author['name'] = data['fullname']

            # Build the affiliation of the author
            if 'affiliation' in data and len(data['affiliation']) > 0:        

                # Build the geographic location of the author
                if data['affiliation']['location']:
                    location = data['affiliation']['location']

                    location_list = list()

                    if 'settlement' in location:
                        location_list.append(location['settlement'])
                    if 'region' in location:
                        location_list.append(location['region'])
                    if 'country' in location:
                        location_list.append(location['country'])

                    author['location'] = ", ".join(location_list)
                else:
                    author['location'] = 'N/A'

                author['institution'] = data['affiliation']['institution'] or 'N/A'
                author['laboratory'] = data['affiliation']['laboratory'] or 'N/A'
            else:
                author['location'] = 'N/A'
                author['institution'] = 'N/A'
                author['laboratory'] = 'N/A'

            #print(author)
            author_list.append(author)

    return author_list

def aggs():
    agg_query = {
                "uniq_sources" : {
                    "cardinality" : {
                        "field" : "source_x.keyword"
                    }
                },
                "uniq_journals": {
                    "cardinality" : {
                        "field" : "journal.keyword"
                    }
                },
                "sources":{
                    "terms":{
                        "field":"source_x.keyword"
                    }
                },
                "journals":{
                    "terms":{
                        "field":"journal.keyword"
                    }
                },
                "uniq_years":{
                    "cardinality" : {
                        "field" : "publish_year"
                    }
                },
                "year":{
                    "terms":{
                        "field":"publish_year"
                    }
                },
                "contains_abstract":{
                    "filters":{
                        "filters": {
                            "abs":{"match":{"abstract.keyword":""}},
                            "fulltext":{"match":{"body_text":""}}
                        }
                    }
                },
                "first":{
                    "cardinality": {
                        "field": "metadata.authors.fullname.keyword"
                    }
                },
                "middle":{
                     "cardinality": {
                        "field": "metadata.authors.middle.keyword"
                    }
                },
                "last":{
                     "cardinality": {
                        "field": "metadata.authors.last.keyword"
                    }
                },
                "full_name":{
                    "terms": {
                        "field": "metadata.authors.fullname.keyword",
                        "size":20,
                        "order" : { "_count" : "desc" }
                    }
                }
            }
    
    return agg_query

def add_source_filters(source):
    source = source.split(',')
    source_filter = {
        "bool":{
            "should":[]
        }
    }
    if len(source)>0:
        for x in source:
            source_filter['bool']['should'].append({
                "match_phrase": {
                    "source_x.keyword": {
                      "query": x
                        }
                    }
                })
    return source_filter


def add_journal_filters(journal):
    journal = journal.split(',')
    journal_filter = {
        "bool":{
            "should":[]
        }
    }
    if len(journal)>0:
        for x in journal:
            journal_filter['bool']['should'].append({
                "match_phrase": {
                    "journal.keyword": {
                      "query": x
                        }
                    }
                })
    return journal_filter


def add_year_filters(year):
    year = year.split(',')
    year_filter = {
        "bool":{
            "should":[]
        }
    }
    if len(year)>0:
        for x in year:
            year_filter['bool']['should'].append({
                "match_phrase": {
                    "publish_year": {
                      "query": x
                        }
                    }
                })
    return year_filter

def add_authors_filters(author):
    author = author.split(',')
    author_filter = {
        "bool":{
            "should":[]
        }
    }

    if len(author)>0:
        for x in author:
            if(x.count(' ') == 1):
                x = x.replace(' ', '  ')

            author_filter['bool']['should'].append({
                "match_phrase": {
                    "metadata.authors.fullname.keyword": {
                      "query": x
                        }
                    }
                })

    return author_filter

def add_keyphrase_filters(keyphrase):
    keyphrase_filter = {
                    "multi_match": {
                            "query": keyphrase,
                            "fields":  ["body_text","abstract^2", "metadata.title^3"],
                            "type": "cross_fields"
                        }
                     }                
    return keyphrase_filter

def remove_punct(my_str):
    punctuations = '''!()-[]{};:'"\,<>./?@#$%^&*_~'''
    # To take input from the user
    # my_str = input("Enter a string: ")

    # remove punctuation from the string
    no_punct = ""
    for char in my_str:
        if char not in punctuations:
            no_punct = no_punct + char

    # display the unpunctuated string
    return no_punct

def remove_stop(query):
    CURRENT_DIRECTORY = os.path.realpath(os.path.dirname(__file__))
    ENGLISH_ST_PATH = os.path.join(CURRENT_DIRECTORY, 'englishST.txt')

    with open(ENGLISH_ST_PATH) as f:
        all_stopwords = f.readlines()
    # you may also want to remove whitespace characters like `\n` at the end of each line
    all_stopwords = [x.strip() for x in all_stopwords] 
    text_tokens = query.split(' ')
    query = [word for word in text_tokens if not word in all_stopwords]
    query = ' '.join(query)
    return query

@api_view(['GET'])
def search(request, query, page):
    
    source = request.GET.get('source') or ''
    journal = request.GET.get('journal') or ''
    full_text = request.GET.get('full_text') or ''
    abstract = request.GET.get('abstract') or ''
    author = request.GET.get('author') or ''
    year = request.GET.get('year') or ''
    keyphrase = request.GET.get('keyphrase') or ''
    nquery = query.lower()
    nquery = remove_punct(nquery)
    nquery = remove_stop(nquery)
    
    # print("Checking query in search:",nquery)
    # print("SOURCE:", source)
    # print("JOURNAL:", journal)
    # print("FULL TEXT:", full_text)
    # print("ABSTRACT:", abstract)
    # print("AUTHOR:", author)

    
    
    size = 15
    start = (page - 1) * size

    body = {
        "from": start,
        "size": size,
        "query": {
            "bool": {
                "filter": [
                    {
                    "multi_match": {
                            "query": nquery,
                            "fields":  ["body_text","abstract^2", "metadata.title^3"],
                            "type": "cross_fields"
                        }
                     }
                ],
                "must":[]
            }
        },
        "aggs" : aggs(),
        'highlight': {'fields': {'body_text': {}, 'abstract.text': {}}}
    }

    if source:
        body['query']['bool']['must'].append(add_source_filters(source))
    if journal:
        body['query']['bool']['must'].append([add_journal_filters(journal)])
    if year:
        body['query']['bool']['must'].append(add_year_filters(year))
    if author:
        body['query']['bool']['must'].append(add_authors_filters(author))
    if keyphrase:
        body['query']['bool']['filter'].append(add_keyphrase_filters(keyphrase))
    
    # if len(filter_query)>0:
    #     for each_filter in filter_query:
    #         body['query']['bool']['must'].append(each_filter)
    #     #body['query']['bool']['minimum_should_match'] = 1
    #     body = body

    res = es.search(index=ELASTIC_INDEX, body=body)
    #print("RESULTS", res)
    #print("RESULTS keys", res['hits']['total']['value'])

    if not res.get('hits') or len(res) == 0 or res['hits']['total']['value'] == 0:
        raise Http404("Search query yields no results")
    else:
        # print("search done")
        totalresultsNumFound = res['hits']['total']['value']
        # hlresults=r.json()['highlighting']
        results = res['hits']['hits']
        aggregations = res['aggregations']
        # print('Got :',res['hits']['total']['value'])
        SearchResults = []
        if len(results) > 0:
            for result in results:
                resultid = result['_id']
                f = {'resultid' : resultid}  # calling the object class that is defined inside models.py
                f['title'] = result['_source']['metadata']['title']

                if len(f['title']) == 0:
                    continue

                f['content'] = result['_source']['body_text']
                """
                if len(result['_source']['metadata']['authors'])>0:
                    if 'affiliation' in result['_source']['metadata']['authors'] and 'location' in result['_source']['metadata']['authors'][0]['affiliation']:
                        f['affiliation'] = result['_source']['metadata']['authors'][0]['affiliation']['location']
                else:
                    f['affiliation'] = ''
                """
                # rawpath= result['_source']['file']['url']

                # removing local folder path
                f['url'] = result['_source']['metadata']['title']
                f['title'] = result['_source']['metadata']['title']
                f['year'] = result['_source']['publish_year']
                f['keyphrases'] = result['_source']['keyphrases']

                f['authors'] = __get_author_list(result)

                # f.description = str(result['_source']['meta']['raw']['description'])
                f['description'] = ''
                if 'highlight' in result:
                    if 'body_text' in result['highlight']:
                        for desc in result['highlight']['body_text']:
                            f['description'] = f['description'] + desc + '\n'

                # f.description = " ".join(f.description).encode("utf-8")
                '''
                if len(result.get('category',[])) > 0:
                   f.category=result['category'][0].encode("utf-8") 
                '''
                # trying to use the location field to get the file name to display the image
                # f.filename= str(imageid)+'.png'
                f['doi'] = result['_source']['doi']
                f['source'] = result['_source']['source_x']
                f['keyphrases'] = result['_source']['keyphrases']
                f['journal'] = result['_source']['journal']
                if not f['journal']:
                    f['journal'] = 'N/A'

                SearchResults.append(f)
                
            context = dict()
            context['results'] = SearchResults

            # Adding aggregations
            filters = {
                'journal': {'displayName': 'Journal'},
                'source': {'displayName': 'Source'},
                'abstract': {'displayName': 'Abstract'},
                'full_text': {'displayName': 'Full Text'},
                'author': {'displayName': 'Author'},
                'year': {'displayName': 'Year'}
            }

            filters['journal']['total'] = aggregations['uniq_journals']['value']
            filters['source']['total'] = aggregations['uniq_sources']['value']
            filters['author']['total'] = aggregations['first']['value']
            filters['year']['total'] = aggregations['uniq_years']['value']
            filters['abstract']['total'] = totalresultsNumFound
            filters['full_text']['total'] = totalresultsNumFound

            no_abstracts_count = aggregations['contains_abstract']['buckets']['abs']['doc_count']
            no_fulltext_count = aggregations['contains_abstract']['buckets']['fulltext']['doc_count']

            filters['abstract']['options'] = [
                {'name': 'True', 'count': totalresultsNumFound - no_abstracts_count},
                {'name': 'False', 'count': no_abstracts_count}
            ]
            
            filters['full_text']['options'] = [
                {'name': 'True', 'count': totalresultsNumFound - no_fulltext_count},
                {'name': 'False', 'count': no_fulltext_count}
            ]

            #Adding list of sources
            total_sources = len(res['aggregations']['sources']['buckets'])
            sources =[]
            if (total_sources > 0):
                for src in res['aggregations']['sources']['buckets']:
                    if src['key'] =='':
                        src['key']= "Unknown"
                    sources.append({'name':src['key'],'count':src['doc_count']})
            
            #Adding list of journals
            total_journals = len(res['aggregations']['journals']['buckets'])
            jnls =[]
            if (total_journals > 0):
                for jnl in res['aggregations']['journals']['buckets']:
                    if jnl['key'] =='':
                        continue
                    jnls.append({'name':jnl['key'],'count':jnl['doc_count']})                                
            #Adding list of years
            total_years = len(res['aggregations']['year']['buckets'])

            yrs =[]
            if (total_years > 0):
                for yr in res['aggregations']['year']['buckets']:
                    if yr['key'] =='':
                        continue
                    yrs.append({'name':yr['key'],'count':yr['doc_count']})

            filters['source']['options'] = sources
            filters['journal']['options'] = jnls
            filters['year']['options'] =  yrs

            #Adding authors to the list
            auths =[]
            fullname = res['aggregations']['full_name']['buckets']
            for name in fullname:
                if not name['key'].replace(' ', '').isalpha():
                    continue
                auths.append({'name':name['key'],'count':name['doc_count']})

            filters['author']['options'] = auths
            context['filters'] = filters
            #print(context)
            # return render(request, 'seer/results.html', context)

            context['total'] = totalresultsNumFound
            context['pageSize'] = size
            context['position'] = start + 1
            context['nextResults'] = len(results) + start
            context['prevResults'] = start - size

            context['page'] = (context['position'] // size) + 1
            context['nextPage'] = max(page + 1, 1)
            context['prevPage'] = page - 1

            numPages = (totalresultsNumFound // size) + 1

            if context['page'] <= 4:
                context['prevPageLimit'] = 1
            else:
                context['prevPageLimit'] = context['page'] - 4

            diff = numPages - context['page']

            if numPages - context['page'] < 4:
                context['nextPageLimit'] = context['page'] + diff
            elif context['prevPageLimit'] < 2:
                context['nextPageLimit'] = min(9, numPages)
            else:
                context['nextPageLimit'] = context['page'] + 4

            context['prevPageList'] = [i for i in range(context['prevPageLimit'], context['page'])]
            context['nextPageList'] = [i for i in range(context['page'] + 1, context['nextPageLimit'] + 1)]
            
            return Response({"context": context})

        else:
            raise Http404("Search query yields no results")



def Query(request):
    if request.method == 'GET':
        query = request.GET.get('query')
        page = int(request.GET.get('page', 1)) or 1

        if query is not None and len(query) > 1:
            # return __search(request, q, start, source, journal, full_text, abstract, author)
            return render(request, 'seer/results.html', {'query': query, 'page': page})
        else:
            return render(request, 'seer/index.html', {})


def Document(request, document_id):
    body = {
        "query": {
            "match": {
                "_id": document_id
            }
        }
    }
    res = es.search(index=ELASTIC_INDEX, body=body)
    results = res['hits']['hits']

    if len(results) == 0:
        raise Http404("Document does not exist")

    result = results[0]

    context = dict()
    context['docId'] = document_id
    context['title'] = result['_source']['metadata']['title']
    context['authors'] = __get_author_list(result)

    context['abstract'] = result['_source']['abstract']
    context['body'] = result['_source']['body_text']
    context['doi'] = result['_source']['doi']
    context['json'] = json.dumps(result, separators=(',', ':'))
    context['source'] = result['_source']['source_x']
    context['journal'] = result['_source']['journal']
    context['year'] = result['_source']['publish_year']
    context['similar_papers'] = ','.join(result['_source']['similar_papers'])

    if not context['journal']:
        context['journal'] = 'N/A'
    return render(request, 'seer/document.html', context)


def DocumentJson(request, document_id):
    body = {
        "query": {
            "match": {
                "_id": document_id
            }
        }
    }
    res = es.search(index=ELASTIC_INDEX, body=body)
    results = res['hits']['hits']

    if len(results) == 0:
        raise Http404("Document does not exist")

    return HttpResponse(json.dumps(results[0], sort_keys=True, indent=4), content_type="application/json")

@api_view(['GET'])
def get_recommendations(request, similar_papers):
    # print("SIMILAR PAPERS:", similar_papers)
    similar_papers = similar_papers.split(',')

    # print("SIMILAR PAPERS:", similar_papers)
    body = {
        "query" : {
            "terms" : {
                "cord_uid" : similar_papers, #query is an array of similar papers like this ["krb1eidw","italbsed"],
                "boost" : 1.0
            }
        }
    }
    res = es.search(index=ELASTIC_INDEX, body=body)
    results = res['hits']['hits']

    if len(results) == 0:
        raise Http404("No similar papers available")
    else:
        recommendations=[]
        for result in results:
            paper = dict()
            paper['doc_id'] = result['_id']
            paper['title'] = result['_source']['metadata']['title']
            paper['abstract'] =  result['_source']['abstract']
            paper['author'] = [author['fullname'] for author in result['_source']['metadata']['authors']]
            paper['year'] = result['_source']['publish_year']
            paper['doi'] =  result['_source']['doi']
            paper['journal'] =  result['_source']['journal']
            recommendations.append(paper)
    
    return HttpResponse(json.dumps({"recom":recommendations}, sort_keys=True, indent=4), content_type="application/json")


    """
    Generic function to search within the list of filters.
    Pass jrnl in query from frontend to search in journals and athr for authors
    query:field to apply search on
    tosearch: keyword to search
    Usage: search_in_filters(request,"jrnl","Virology")
    """
    def search_in_filters(request,query,tosearch):
        if query=='jrnl':
            key_to_search = "journal"
        elif query=='athr':
            key_to_search ="metadata.authors.fullname"

        body = {       
            "_source": "",
            "query":{
                "query_string":{
                    "default_field" : key_to_search, "query" : "*"+tosearch+"*"
                }
            },
            "highlight": {
            "pre_tags": [""], 
            "post_tags": [""], 
            "fields": {
                key_to_search: {}
            }
            }
        }
        # print(body)
        response = es.search(index=ELASTIC_INDEX, body=body)
        results = response['hits']['hits']
        # print("In search_in_filters: ",len(results))

        if len(results) == 0:
            raise Http404("No results available")
        else:
            searchlist = []
            for result in results:
                searchlist += result['highlight'][key_to_search]
                if len(list(set(searchlist)))>=10:
                    break
            searchlist = list(set(searchlist))
            searchlist = searchlist[:10]
            # print("Searchresult:",searchlist)
        return HttpResponse(json.dumps({"searched":searchlist}, sort_keys=True, indent=4), content_type="application/json")
