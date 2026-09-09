package com.ragstudy.model.vo;

public class LoginVO {

    private String accessToken;
    private String tokenType;
    private long expiresIn;
    private UserInfoVO userInfo;

    public LoginVO() {}

    public String getAccessToken() { return accessToken; }
    public void setAccessToken(String accessToken) { this.accessToken = accessToken; }
    public String getTokenType() { return tokenType; }
    public void setTokenType(String tokenType) { this.tokenType = tokenType; }
    public long getExpiresIn() { return expiresIn; }
    public void setExpiresIn(long expiresIn) { this.expiresIn = expiresIn; }
    public UserInfoVO getUserInfo() { return userInfo; }
    public void setUserInfo(UserInfoVO userInfo) { this.userInfo = userInfo; }

    public static Builder builder() { return new Builder(); }

    public static class Builder {
        private String accessToken;
        private String tokenType = "Bearer";
        private long expiresIn;
        private UserInfoVO userInfo;

        public Builder accessToken(String accessToken) { this.accessToken = accessToken; return this; }
        public Builder tokenType(String tokenType) { this.tokenType = tokenType; return this; }
        public Builder expiresIn(long expiresIn) { this.expiresIn = expiresIn; return this; }
        public Builder userInfo(UserInfoVO userInfo) { this.userInfo = userInfo; return this; }

        public LoginVO build() {
            LoginVO vo = new LoginVO();
            vo.accessToken = this.accessToken;
            vo.tokenType = this.tokenType;
            vo.expiresIn = this.expiresIn;
            vo.userInfo = this.userInfo;
            return vo;
        }
    }
}