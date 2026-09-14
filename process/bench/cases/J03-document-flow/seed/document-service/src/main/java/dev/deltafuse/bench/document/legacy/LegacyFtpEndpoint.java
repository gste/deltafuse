package dev.deltafuse.bench.document.legacy;

/** Connection details of the retired FTP drop; replaced by the live upload API. */
public record LegacyFtpEndpoint(String host, int port, String directory, boolean passive) {

    public LegacyFtpEndpoint {
        if (port <= 0 || port > 65535) {
            throw new IllegalArgumentException("port out of range");
        }
    }

    public String uri() {
        return "ftp://" + host + ":" + port + "/" + directory;
    }
}
