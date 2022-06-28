import urllib.request
def connect_on(host):
    try:
        urllib.request.urlopen(host)
        return True
    except:
        return False