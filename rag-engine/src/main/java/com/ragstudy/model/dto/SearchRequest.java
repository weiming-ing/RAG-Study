package com.ragstudy.model.dto;

import jakarta.validation.constraints.NotBlank;
import java.util.Map;

public class SearchRequest {

    @NotBlank(message = "查询内容不能为空")
    private String query;

    private int topK = 10;
    private boolean enableHybrid = true;
    private int rerankTopK = 0;
    private Map<String, String> filters;

    public String getQuery() { return query; }
    public void setQuery(String query) { this.query = query; }
    public int getTopK() { return topK; }
    public void setTopK(int topK) { this.topK = topK; }
    public boolean isEnableHybrid() { return enableHybrid; }
    public void setEnableHybrid(boolean enableHybrid) { this.enableHybrid = enableHybrid; }
    public int getRerankTopK() { return rerankTopK; }
    public void setRerankTopK(int rerankTopK) { this.rerankTopK = rerankTopK; }
    public Map<String, String> getFilters() { return filters; }
    public void setFilters(Map<String, String> filters) { this.filters = filters; }
}