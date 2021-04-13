import newspaper
import os
import pandas
import requests
from pyvis.network import Network
import networkx as nx
from networkx.algorithms import community
from operator import itemgetter
from ast import literal_eval
from pyvis.network import Network
from jaal import Jaal
from jaal.datasets import load_got
import plotly.offline as py
import plotly.graph_objects as go


def listParser(dir_name, article_name):
    article_array = []
    #list_location = input("Where is your articles.txt? Leave blank for current")
    #if (list_location == None):
    #    dir_name = list_location

    if os.path.exists(dir_name + "\\" + article_name):
        file = open(dir_name + "\\" + article_name, "r")
        try:
            for i in file:
                article_array.append(i.rstrip())
        except:
            print("missing articles")
            quit()
    else:
        print("Could not find " + (dir_name + "\\" + article_name) + "file missing or mis-named")
        quit()

    return article_array

def databaseCheck(dir_name, database_name, article_array):
    print("checking database")

    database_array = []
    if not os.path.exists(dir_name + "\\" + database_name):
        database = pandas.DataFrame(columns = ['url','title','authors','keywords'])
        database.to_csv(database_name, index=False)

    reader = pandas.read_csv(database_name)
    database_array = reader['url'].values

    #print(database_array)
    return (set(article_array) - set(database_array))


def downloadArticles(articles_to_download, database_name):
    print("downloading articles")

    articles_to_download = list(articles_to_download)
    if (len(articles_to_download) == 0):
        print("no new articles to add")
        return

    pool = []
    for i in articles_to_download:
        pool.append(newspaper.Article(i))
    newspaper.news_pool.set(pool, threads_per_source=1)
    newspaper.news_pool.join()

    database = pandas.DataFrame(columns = ['url','title','authors','keywords'])
    x = 0
    for i in pool:
        try:
            i.parse()
            i.nlp()
            database = database.append({'url': articles_to_download[x], 
                                        'title': i.title,
                                        'authors': i.authors,
                                        'keywords': i.keywords}, ignore_index=True)
            x += 1
        except:
            x += 1
            continue    
        

    database.to_csv(database_name, mode='a', header=False, index=False)



def verifyURLS(articles_to_download):
    print("article definitions")
    headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.107 Safari/537.36' }
    to_remove = []
    for i in articles_to_download:
        try:
            code = requests.get(i, headers=headers).status_code
            #print(code, i)
            if code != 200:
                to_remove.append(i)
        except:
            to_remove.append(i)
            
    for i in to_remove:
        articles_to_download.remove(i)
    
    return articles_to_download

def nodeList(database_name):
    reader = pandas.read_csv(database_name)
    reader = reader[['url','title']]
    reader.rename(columns={'url':'ID','title':'Name'}, inplace=True)
    #print(reader)
    return reader

def edgeList(database_name):
    reader = pandas.read_csv(database_name)
    reader = reader[['url','keywords']]
    reader['keywords'] = reader['keywords'].apply(literal_eval)
    df_edges = pandas.DataFrame(columns=['Source','Target','Weight'])
    for index, x in enumerate(reader['keywords']):
        #print("INDEX", index, x)
        offset = 1
        for y in reader['keywords'][index + offset:]:
            #print(y)
            matches = set(x) & set(y)
            if len(matches) > 0:
                #print("MATCH DATA", index, offset, len(matches), matches, x, y)
                df_edges = df_edges.append({'Source':reader['url'][index], 'Target':reader['url'][index + offset], 'Weight': len(matches)}, ignore_index=True)
            offset += 1
        #print(x)

    #pandas.set_option("display.max_rows", None, "display.max_columns", None)
    #print(df_edges)

    return df_edges

def nxCommunities(G):
    
    communities = community.greedy_modularity_communities(G)
    modularity_dict = {}
    for i,c in enumerate(communities):
        for name in c:
            modularity_dict[name] = i
    nx.set_node_attributes(G, modularity_dict, 'modularity')

    class0 = [n for n in G.nodes() if G.nodes[n]['modularity'] == 0]

    for i,c in enumerate(communities):
        if len(c) > 2:
            print('Class '+str(i)+':', list(c))

def nxGeneration(node_list, edge_list):
    G = nx.Graph()
    G = nx.from_pandas_edgelist(edge_list, 'Source', 'Target', edge_attr='Weight')
    #nx.set_node_attributes(G, node_list.set_index('ID').to_dict('index'))
    nx.set_node_attributes(G, node_list.set_index('ID'), 'index')
    #nx.set_node_attributes(G, node_list.set_index('Name'), 'Title')

    #print(nx.info(G), G.nodes, G.edges)
    #print(G.nodes)
    #print(G.edges(data=True))
    #nxCommunities(G)


    pos_ = nx.kamada_kawai_layout(G)

    node_trace = go.Scatter(x = [],
                        y = [],
                        text = [],
                        textposition = "top center",
                        textfont_size = 10,
                        mode = 'markers+text',
                        marker = dict(color = [],
                                    size  = [],
                                    line  = None)
                        )
# For each node in midsummer, get the position and size and add to the node_trace
    for node in G.nodes():
        #print(nx.get_node_attributes(G, node))
        x, y = pos_[node]
        node_trace['x'] += tuple([x])
        node_trace['y'] += tuple([y])
        node_trace['marker']['color'] += tuple(['blue'])
        node_trace['marker']['size'] += tuple([12])
        node_trace['text'] += tuple(['<b>' + node + '</b>'])
    
    layout = go.Layout(
        hovermode="closest",
        hoverdistance=10,
        clickmode="event+select",
        paper_bgcolor='white',
        plot_bgcolor='white'
        )

    edge_trace = []
    for edge in G.edges():
        #print(G.edges()[edge]['Weight'])
        char_1 = edge[0]
        char_2 = edge[1]

        x0, y0 = pos_[char_1]
        x1, y1 = pos_[char_2]
        
        trace = make_edge([x0, x1, None], [y0, y1, None], .2*int(G.edges()[edge]['Weight']))
        edge_trace.append(trace)

    fig = go.Figure(layout = layout)

    for trace in edge_trace:
        fig.add_trace(trace)

    fig.add_trace(node_trace)

    fig.update_layout(showlegend = False)

    fig.update_xaxes(showticklabels = True)

    fig.update_yaxes(showticklabels = True)

    #fig.show()
    py.plot(fig, filename='plotly.html')


def jaal(node_list, edge_list):
    node_list.rename(columns={"ID":"id"}, inplace=True)
    edge_list.rename(columns={"Source":"from","Target":"to"}, inplace=True)
    print(node_list)
    print(edge_list)
    Jaal(edge_list, node_list).plot()

def plotly(node_list, edge_list):
    G = nx.Graph()
    G = nx.from_pandas_edgelist(edge_list, 'Source', 'Target', edge_attr='Weight')
    nx.set_node_attributes(G, node_list.set_index('ID').to_dict('index'))
    #print(nx.info(G))

def make_edge(x, y, width):
    return go.Scatter(x = x,
                        y = y,
                        line = dict(width = width, color = 'slategray'),
                        hoverinfo = 'text',
                        #text = ([text]),
                        mode = 'lines')

def pyVIS(node_list, edge_list):
    G = nx.Graph()
    G = nx.from_pandas_edgelist(edge_list, 'Source', 'Target', edge_attr='Weight')
    
    nx.set_node_attributes(G, node_list.set_index('ID').to_dict('index'))
    net = Network(height=1500, width=1300, notebook=True)
    net.toggle_hide_edges_on_drag=False
    net.show_buttons(filter_=['physics','interaction','manuipulation', 'nodes'])
    net.from_nx(G)
    
    
    net.show("pyvis.html")

def main():
    article_name = "articles.txt"
    database_name = "database.csv"
    dir_name = os.path.dirname(os.path.realpath(__file__))

    article_array = listParser(dir_name, article_name)
    #print(article_array)

    articles_to_download = databaseCheck(dir_name, database_name, article_array)
    #print(articles_to_download)

    articles_to_download = verifyURLS(articles_to_download)

    downloadArticles(articles_to_download, database_name)

    node_list = nodeList(database_name)
    #print(node_list)
    edge_list = edgeList(database_name)

    #plotly(node_list, edge_list)

    #jaal(node_list, edge_list)
    pyVIS(node_list, edge_list)

    #nxGeneration(node_list, edge_list)

    #visGeneration(G)
    
main()

