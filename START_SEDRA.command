#!/bin/sh
# macOS: double-click in Finder. Opens Terminal, starts SEDRA (see start_sedra.sh). If macOS refuses the first start ("kann nicht geöffnet werden"),
# once: right-click -> Öffnen, or in Terminal: chmod +x START_SEDRA.command start_sedra.sh
cd "$(dirname "$0")"
exec sh ./start_sedra.sh "$@"     # ueber sh: laeuft auch, wenn das ZIP die Ausfuehrungsrechte verloren hat
