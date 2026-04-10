FROM nodered/node-red:latest

# 1. Ci spostiamo nel "cuore" di Node-RED (fuori dalla portata del volume di Windows)
WORKDIR /usr/src/node-red

# 2. Installiamo la Dashboard 2.0 qui dentro, così è protetta!
RUN npm install --no-audit --no-update-notifier --no-fund --only=production \
    @flowfuse/node-red-dashboard

# 3. Copiamo il package.json e installiamo le dipendenze del progetto
WORKDIR /data
COPY package.json /data/package.json
RUN npm install --no-audit --no-update-notifier --no-fund --only=production

# 4. Copiamo il tuo file. (Nota: questo verrà comunque coperto se usi il volume, vedi lo Step 2!)
COPY --chown=node-red:node-red ./project/NodeRed_ProjectV4.json /data/flows.json