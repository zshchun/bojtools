def extract_text(tags):
    ret = ''
    for t in tags:
        ret += "".join([x.replace('\t', '') for x in t.itertext()])
    return ret
