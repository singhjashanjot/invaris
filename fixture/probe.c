#define _POSIX_C_SOURCE 200809L
#include <netdb.h>
#include <openssl/err.h>
#include <openssl/ssl.h>
#include <openssl/sslerr.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

static int failure(const char *stage, SSL_CTX *context, SSL *session, int connection) {
    printf("{\"connected\":false,\"verify_ok\":false,\"app_valid\":false,\"error\":\"%s\"}\n", stage);
    if (session) SSL_free(session);
    if (context) SSL_CTX_free(context);
    if (connection >= 0) close(connection);
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    if (strcmp(argv[1], "X25519") && strcmp(argv[1], "X25519MLKEM768") && strcmp(argv[1], "X25519MLKEM768:X25519")) return 2;
    signal(SIGPIPE, SIG_IGN);
    SSL_CTX *context = SSL_CTX_new(TLS_client_method());
    if (!context) return failure("context", NULL, NULL, -1);
    SSL_CTX_set_verify(context, SSL_VERIFY_PEER, NULL);
    SSL_CTX_set_session_cache_mode(context, SSL_SESS_CACHE_OFF);
    if (!SSL_CTX_set_min_proto_version(context, TLS1_3_VERSION) ||
        !SSL_CTX_set_max_proto_version(context, TLS1_3_VERSION) ||
        !SSL_CTX_set1_groups_list(context, argv[1]) ||
        SSL_CTX_load_verify_locations(context, argv[2], NULL) != 1) return failure("configuration", context, NULL, -1);
    struct addrinfo hints = {0}, *addresses = NULL;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo("fixture", "8443", &hints, &addresses)) return failure("dns", context, NULL, -1);
    int connection = socket(addresses->ai_family, addresses->ai_socktype, addresses->ai_protocol);
    struct timeval timeout = {.tv_sec = 5, .tv_usec = 0};
    if (connection >= 0) {
        setsockopt(connection, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
        setsockopt(connection, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    }
    int connect_result = connection >= 0 ? connect(connection, addresses->ai_addr, addresses->ai_addrlen) : -1;
    freeaddrinfo(addresses);
    if (connect_result) return failure("connect", context, NULL, connection);
    SSL *session = SSL_new(context);
    if (!session) return failure("session", context, NULL, connection);
    if (SSL_set_fd(session, connection) != 1 || SSL_set_tlsext_host_name(session, "fixture") != 1 ||
        SSL_set1_host(session, "fixture") != 1) return failure("verification_parameters", context, session, connection);
    ERR_clear_error();
    int handshake_result = SSL_connect(session);
    if (handshake_result != 1) {
        int ssl_error = SSL_get_error(session, handshake_result);
        unsigned long error_code = ERR_peek_last_error();
        const char *reason = "handshake_transport_error";
        if (SSL_get_verify_result(session) != X509_V_OK) reason = "certificate_verification";
        else if (ssl_error == SSL_ERROR_SSL && ERR_GET_LIB(error_code) == ERR_LIB_SSL &&
                 ERR_GET_REASON(error_code) == SSL_R_SSLV3_ALERT_HANDSHAKE_FAILURE) reason = "handshake_rejected";
        return failure(reason, context, session, connection);
    }
    if (SSL_get_verify_result(session) != X509_V_OK) return failure("certificate_verification", context, session, connection);
    if (SSL_session_reused(session)) return failure("resumed_session", context, session, connection);
    const char *raw_group = SSL_get0_group_name(session);
    const char *group = NULL;
    if (raw_group && !strcasecmp(raw_group, "X25519")) group = "X25519";
    if (raw_group && !strcasecmp(raw_group, "X25519MLKEM768")) group = "X25519MLKEM768";
    if (!group) return failure("unknown_group", context, session, connection);
    const char *request = "GET /health HTTP/1.1\r\nHost: fixture\r\nConnection: close\r\n\r\n";
    if (SSL_write(session, request, (int)strlen(request)) <= 0) return failure("write", context, session, connection);
    char response[4096] = {0};
    size_t total = 0;
    while (total < sizeof(response) - 1) {
        int count = SSL_read(session, response + total, (int)(sizeof(response) - 1 - total));
        if (count <= 0) break;
        total += (size_t)count;
    }
    char *body = strstr(response, "\r\n\r\n");
    if (strncmp(response, "HTTP/1.1 200 OK\r\n", 17) || !body) return failure("application", context, session, connection);
    body += 4;
    size_t body_length = strlen(body);
    if (body_length < 2 || body[0] != '{' || body[body_length - 1] != '}') return failure("application_json", context, session, connection);
    printf("{\"connected\":true,\"verify_ok\":true,\"fresh\":true,\"session_reused\":false,\"protocol\":\"%s\",\"observed_group\":\"%s\",\"openssl_version\":\"%s\",\"application\":%s}\n", SSL_get_version(session), group, OpenSSL_version(OPENSSL_VERSION), body);
    SSL_shutdown(session);
    SSL_free(session);
    SSL_CTX_free(context);
    close(connection);
    return 0;
}
