package com.ragstudy.model.vo;

import java.util.List;

public class SearchResponseVO {

    private List<SearchResultVO> results;
    private double latency;
    private int totalHits;

    public SearchResponseVO() {}

    public List<SearchResultVO> getResults() { return results; }
    public void setResults(List<SearchResultVO> results) { this.results = results; }
    public double getLatency() { return latency; }
    public void setLatency(double latency) { this.latency = latency; }
    public int getTotalHits() { return totalHits; }
    public void setTotalHits(int totalHits) { this.totalHits = totalHits; }

    public static Builder builder() { return new Builder(); }

    public static class Builder {
        private List<SearchResultVO> results;
        private double latency;
        private int totalHits;

        public Builder results(List<SearchResultVO> results) { this.results = results; return this; }
        public Builder latency(double latency) { this.latency = latency; return this; }
        public Builder totalHits(int totalHits) { this.totalHits = totalHits; return this; }

        public SearchResponseVO build() {
            SearchResponseVO vo = new SearchResponseVO();
            vo.results = this.results;
            vo.latency = this.latency;
            vo.totalHits = this.totalHits;
            return vo;
        }
    }
}