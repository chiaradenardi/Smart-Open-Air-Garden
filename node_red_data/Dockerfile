FROM nodered/node-red:latest
WORKDIR /data
COPY package.json /data/package.json
RUN npm install --no-audit --no-update-notifier --no-fund
COPY flows.json /data/flows.json
COPY flows_cred.json /data/flows_cred.json