import urllib.request

url = 'https://staticmap.openstreetmap.de/staticmap.php?center=40.7143,-74.006&zoom=6&size=640x260&markers=40.7143,-74.006,red-pushpin'
print(url)
resp = urllib.request.urlopen(url)
print(resp.status)
print(resp.info().get_content_type())
with open('tmp_map_response.bin', 'wb') as f:
    f.write(resp.read())
print('saved', 'tmp_map_response.bin')
