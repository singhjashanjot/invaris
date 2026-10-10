#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <openssl/err.h>
#include <openssl/ssl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

static int safe_identity(const char *value) {
    size_t length = strlen(value);
    if (length < 1 || length > 128) return 0;
    for (size_t index = 0; index < length; index++) {
        char character = value[index];
        if (!((character >= 'a' && character <= 'z') || (character >= '0' && character <= '9') || character == '-')) return 0;
    }
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 6 || !safe_identity(argv[2]) || !safe_identity(argv[3])) return 2;
    if (strcmp(argv[1], "X25519") && strcmp(argv[1], "X25519MLKEM768")) return 2;
    signal(SIGPIPE, SIG_IGN);
    SSL_CTX *context = SSL_CTX_new(TLS_server_method());
    if (!context) return 3;
    if (!SSL_CTX_set_min_proto_version(context, TLS1_3_VERSION) ||
        !SSL_CTX_set_max_proto_version(context, TLS1_3_VERSION) ||
        !SSL_CTX_set1_groups_list(context, argv[1]) ||
        SSL_CTX_use_certificate_chain_file(context, argv[4]) != 1 ||
        SSL_CTX_use_PrivateKey_file(context, argv[5], SSL_FILETYPE_PEM) != 1 ||
        SSL_CTX_check_private_key(context) != 1) {
        ERR_print_errors_fp(stderr);
        SSL_CTX_free(context);
        return 3;
    }
    SSL_CTX_set_session_cache_mode(context, SSL_SESS_CACHE_OFF);
    SSL_CTX_set_num_tickets(context, 0);
    int listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) { SSL_CTX_free(context); return 4; }
    int enabled = 1;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &enabled, sizeof(enabled));
    struct sockaddr_in address = {0};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_ANY);
    address.sin_port = htons(8443);
    if (bind(listener, (struct sockaddr *)&address, sizeof(address)) || listen(listener, 16)) {
        close(listener); SSL_CTX_free(context); return 4;
    }
    for (;;) {
        int connection = accept(listener, NULL, NULL);
        if (connection < 0) { if (errno == EINTR) continue; break; }
        struct timeval timeout = {.tv_sec = 5, .tv_usec = 0};
        setsockopt(connection, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
        setsockopt(connection, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
        SSL *session = SSL_new(context);
        if (!session) { close(connection); continue; }
        SSL_set_fd(session, connection);
        if (SSL_accept(session) == 1) {
            char request[2048] = {0};
            int count = SSL_read(session, request, sizeof(request) - 1);
            if (count > 0 && !strncmp(request, "GET /health HTTP/1.", 18)) {
                char body[512];
                int length = snprintf(body, sizeof(body), "{\"status\":\"ok\",\"candidate_digest\":\"%s\",\"instance_id\":\"%s\"}", argv[2], argv[3]);
                char response[1024];
                int total = snprintf(response, sizeof(response), "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s", length, body);
                if (length > 0 && length < (int)sizeof(body) && total > 0 && total < (int)sizeof(response)) {
                    int sent = 0;
                    while (sent < total) { int written = SSL_write(session, response + sent, total - sent); if (written <= 0) break; sent += written; }
                }
            }
            SSL_shutdown(session);
        }
        SSL_free(session);
        close(connection);
    }
    close(listener);
    SSL_CTX_free(context);
    return 0;
}

