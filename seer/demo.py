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
    with open('/data/CoronaSeer/seer/englishST.txt') as f:
        all_stopwords = f.readlines()
    # you may also want to remove whitespace characters like `\n` at the end of each line
    all_stopwords = [x.strip() for x in all_stopwords] 
    text_tokens = query.split(' ')
    query = [word for word in text_tokens if not word in all_stopwords]
    query = ' '.join(query)
    return query

query = 'This result suggests that Amph-FL is capable of driving membrane fission, a more energetically demanding To make this comparison, we created a chimeric protein that places the two mechanisms in direct competition This result suggests that crowding among disordered domains and scaffolding by BAR domains make comparable This result suggests that assembly of the I-BAR scaffold stabilized the membrane against shedding. This result demonstrates that, under appropriate conditions, steric pressure among crowded disordered'

query = query.lower()
query = remove_punct(query)
query = remove_stop(query)

print(query)