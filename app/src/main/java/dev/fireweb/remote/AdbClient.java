package dev.fireweb.remote;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;

import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.math.BigInteger;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Collections;
import java.util.Enumeration;

import javax.crypto.Cipher;

public class AdbClient {
    private static final int A_CNXN = 0x4e584e43;
    private static final int A_OPEN = 0x4e45504f;
    private static final int A_OKAY = 0x59414b4f;
    private static final int A_CLSE = 0x45534c43;
    private static final int A_WRTE = 0x45545257;
    private static final int A_AUTH = 0x48545541;

    private static final int ADB_VERSION = 0x01000000;
    private static final int MAX_DATA = 4096;

    private static final int AUTH_TOKEN = 1;
    private static final int AUTH_SIGNATURE = 2;
    private static final int AUTH_RSAPUBLICKEY = 3;

    private static final byte[] SHA1_DIGEST_INFO_PREFIX = new byte[] {
            0x30, 0x21, 0x30, 0x09, 0x06, 0x05, 0x2b, 0x0e,
            0x03, 0x02, 0x1a, 0x05, 0x00, 0x04, 0x14
    };

    private static final byte[] SIGNATURE_PADDING = createSignaturePadding();

    private final Context context;
    private final KeyPair keyPair;

    public AdbClient(Context context) throws Exception {
        this.context = context.getApplicationContext();
        this.keyPair = loadOrCreateKeyPair();
    }

    public synchronized String shell(String command, int timeoutMs) throws Exception {
        Exception last = null;
        String[] hosts = new String[] { "127.0.0.1", getLanIp() };
        for (String host : hosts) {
            if (host == null || host.length() == 0) continue;
            try {
                return shellOnHost(host, command, timeoutMs);
            } catch (Exception e) {
                last = e;
            }
        }
        if (last != null) throw last;
        throw new IOException("No local ADB address found");
    }

    private String shellOnHost(String host, String command, int timeoutMs) throws Exception {
        Socket socket = new Socket();
        socket.connect(new InetSocketAddress(host, 5555), Math.min(timeoutMs, 5000));
        socket.setSoTimeout(timeoutMs);
        DataInputStream in = new DataInputStream(socket.getInputStream());
        DataOutputStream out = new DataOutputStream(socket.getOutputStream());

        try {
            connect(in, out);
            int localId = 1;
            send(out, A_OPEN, localId, 0, ("shell:" + command + "\0").getBytes("UTF-8"));
            int remoteId = 0;
            ByteArrayOutputStream result = new ByteArrayOutputStream();

            while (true) {
                Packet p = read(in);
                if (p.command == A_OKAY) {
                    remoteId = p.arg0;
                } else if (p.command == A_WRTE) {
                    if (remoteId == 0) remoteId = p.arg0;
                    result.write(p.data);
                    send(out, A_OKAY, localId, remoteId, new byte[0]);
                } else if (p.command == A_CLSE) {
                    if (remoteId == 0) remoteId = p.arg0;
                    send(out, A_CLSE, localId, remoteId, new byte[0]);
                    break;
                } else if (p.command == A_AUTH) {
                    throw new IOException("Unexpected ADB authorization during shell");
                }
            }
            return new String(result.toByteArray(), "UTF-8").trim();
        } finally {
            try { socket.close(); } catch (Exception ignored) {}
        }
    }

    private void connect(DataInputStream in, DataOutputStream out) throws Exception {
        send(out, A_CNXN, ADB_VERSION, MAX_DATA, "host::\0".getBytes("UTF-8"));
        boolean signatureSent = false;
        boolean publicKeySent = false;

        while (true) {
            Packet p = read(in);
            if (p.command == A_CNXN) return;
            if (p.command != A_AUTH || p.arg0 != AUTH_TOKEN) continue;

            if (!signatureSent) {
                byte[] signature = signAdbToken(p.data, (RSAPrivateKey) keyPair.getPrivate());
                send(out, A_AUTH, AUTH_SIGNATURE, 0, signature);
                signatureSent = true;
            } else if (!publicKeySent) {
                byte[] publicKey = adbPublicKey((RSAPublicKey) keyPair.getPublic());
                send(out, A_AUTH, AUTH_RSAPUBLICKEY, 0, publicKey);
                publicKeySent = true;
            } else {
                byte[] signature = signAdbToken(p.data, (RSAPrivateKey) keyPair.getPrivate());
                send(out, A_AUTH, AUTH_SIGNATURE, 0, signature);
            }
        }
    }

    private static byte[] signAdbToken(byte[] token, RSAPrivateKey privateKey) throws Exception {
        if (token.length != 20) throw new IOException("Unexpected ADB token length: " + token.length);
        Cipher cipher = Cipher.getInstance("RSA/ECB/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, privateKey);
        cipher.update(SIGNATURE_PADDING);
        return cipher.doFinal(token);
    }

    private static byte[] createSignaturePadding() {
        byte[] padding = new byte[236];
        padding[0] = 0x00;
        padding[1] = 0x01;
        int digestStart = padding.length - SHA1_DIGEST_INFO_PREFIX.length;
        for (int i = 2; i < digestStart - 1; i++) padding[i] = (byte) 0xff;
        padding[digestStart - 1] = 0x00;
        System.arraycopy(SHA1_DIGEST_INFO_PREFIX, 0, padding, digestStart, SHA1_DIGEST_INFO_PREFIX.length);
        return padding;
    }

    private static byte[] adbPublicKey(RSAPublicKey key) throws Exception {
        final int modulusBytes = 256;
        BigInteger modulus = key.getModulus();
        BigInteger two32 = BigInteger.ONE.shiftLeft(32);
        int modulusWords = modulusBytes / 4;
        BigInteger n0 = modulus.and(two32.subtract(BigInteger.ONE));
        int n0inv = n0.modInverse(two32).negate().intValue();
        BigInteger rr = BigInteger.ONE.shiftLeft(modulusBytes * 8 * 2).mod(modulus);
        byte[] modulusLE = toLittleEndianFixed(modulus, modulusBytes);
        byte[] rrLE = toLittleEndianFixed(rr, modulusBytes);

        ByteBuffer struct = ByteBuffer.allocate(4 + 4 + modulusBytes + modulusBytes + 4)
                .order(ByteOrder.LITTLE_ENDIAN);
        struct.putInt(modulusWords);
        struct.putInt(n0inv);
        struct.put(modulusLE);
        struct.put(rrLE);
        struct.putInt(key.getPublicExponent().intValue());

        String encoded = Base64.encodeToString(struct.array(), Base64.NO_WRAP);
        return (encoded + " fireweb@firetv\0").getBytes("UTF-8");
    }

    private static byte[] toLittleEndianFixed(BigInteger value, int length) throws IOException {
        byte[] src = value.toByteArray();
        int start = (src.length > 1 && src[0] == 0) ? 1 : 0;
        int count = src.length - start;
        if (count > length) throw new IOException("RSA value too large");
        byte[] out = new byte[length];
        for (int i = 0; i < count; i++) out[i] = src[src.length - 1 - i];
        return out;
    }

    private KeyPair loadOrCreateKeyPair() throws Exception {
        SharedPreferences prefs = context.getSharedPreferences("adb_keys", Context.MODE_PRIVATE);
        String privateB64 = prefs.getString("private", null);
        String publicB64 = prefs.getString("public", null);
        KeyFactory factory = KeyFactory.getInstance("RSA");

        if (privateB64 != null && publicB64 != null) {
            try {
                PrivateKey privateKey = factory.generatePrivate(
                        new PKCS8EncodedKeySpec(Base64.decode(privateB64, Base64.DEFAULT)));
                PublicKey publicKey = factory.generatePublic(
                        new X509EncodedKeySpec(Base64.decode(publicB64, Base64.DEFAULT)));
                return new KeyPair(publicKey, privateKey);
            } catch (Exception ignored) {}
        }

        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        KeyPair kp = generator.generateKeyPair();
        prefs.edit()
                .putString("private", Base64.encodeToString(kp.getPrivate().getEncoded(), Base64.NO_WRAP))
                .putString("public", Base64.encodeToString(kp.getPublic().getEncoded(), Base64.NO_WRAP))
                .apply();
        return kp;
    }

    private static void send(DataOutputStream out, int command, int arg0, int arg1, byte[] data)
            throws IOException {
        int checksum = 0;
        for (byte b : data) checksum += (b & 0xff);
        writeLeInt(out, command);
        writeLeInt(out, arg0);
        writeLeInt(out, arg1);
        writeLeInt(out, data.length);
        writeLeInt(out, checksum);
        writeLeInt(out, command ^ 0xffffffff);
        out.write(data);
        out.flush();
    }

    private static Packet read(DataInputStream in) throws IOException {
        byte[] header = new byte[24];
        in.readFully(header);
        ByteBuffer b = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN);
        Packet p = new Packet();
        p.command = b.getInt();
        p.arg0 = b.getInt();
        p.arg1 = b.getInt();
        int length = b.getInt();
        int checksum = b.getInt();
        int magic = b.getInt();

        if ((p.command ^ 0xffffffff) != magic) throw new IOException("Invalid ADB header");
        if (length < 0 || length > 1024 * 1024) throw new IOException("Invalid ADB data length: " + length);

        p.data = new byte[length];
        in.readFully(p.data);
        int actual = 0;
        for (byte value : p.data) actual += (value & 0xff);
        if (actual != checksum) throw new IOException("Invalid ADB checksum");
        return p;
    }

    private static void writeLeInt(DataOutputStream out, int value) throws IOException {
        out.writeByte(value & 0xff);
        out.writeByte((value >>> 8) & 0xff);
        out.writeByte((value >>> 16) & 0xff);
        out.writeByte((value >>> 24) & 0xff);
    }

    private static String getLanIp() {
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            for (NetworkInterface nif : Collections.list(interfaces)) {
                if (!nif.isUp() || nif.isLoopback()) continue;
                for (InetAddress addr : Collections.list(nif.getInetAddresses())) {
                    if (addr instanceof Inet4Address && !addr.isLoopbackAddress() && addr.isSiteLocalAddress()) {
                        return addr.getHostAddress();
                    }
                }
            }
        } catch (Exception ignored) {}
        return null;
    }

    private static class Packet {
        int command;
        int arg0;
        int arg1;
        byte[] data;
    }
}
