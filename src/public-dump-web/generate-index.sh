#!/bin/bash

BUCKET_NAME="otr-public-replica"
INDEX_FILE="/home/stage/prod-dumps-public/web/index.html"

rm $INDEX_FILE || echo "Index file does not exist"

# Generate the HTML header
cat <<EOF > $INDEX_FILE
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Browse: o!TR Public Datasets</title>
</head>
<body>
    <h1>Terms of Use</h1>
    <p>$(cat /home/stage/prod-dumps-public/web/terms-of-use.txt)</p>

    <h1>Files in $BUCKET_NAME</h1>
    <ul>
EOF

# Append the list of file links to the HTML
gcloud storage ls gs://$BUCKET_NAME/ | while read -r OBJECT; do # Changed this line
    FILE_URL="https://storage.googleapis.com/${OBJECT#gs://}"
    echo "        <li><a href=\"$FILE_URL\" download>${OBJECT#gs://}</a></li>" >> $INDEX_FILE
done

# Generate the HTML footer
cat <<EOF >> $INDEX_FILE
    </ul>
</body>
</html>
EOF
