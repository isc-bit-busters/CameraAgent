FROM prosody/prosody:latest

RUN apt-get update && apt-get install -y openssl && apt-get clean

RUN mkdir -p /etc/prosody/certs

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["prosody"]