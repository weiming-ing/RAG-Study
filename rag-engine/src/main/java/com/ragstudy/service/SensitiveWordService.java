package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.model.entity.SensitiveWord;
import com.ragstudy.repository.SensitiveWordMapper;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.*;
import java.util.regex.Pattern;

@Service
public class SensitiveWordService {

    private final SensitiveWordMapper sensitiveWordMapper;
    private volatile List<String> cachedWords = null;
    private volatile long lastCacheTime = 0;
    private static final long CACHE_TTL = 5 * 60 * 1000;

    public SensitiveWordService(SensitiveWordMapper sensitiveWordMapper) {
        this.sensitiveWordMapper = sensitiveWordMapper;
    }

    public IPage<SensitiveWord> list(int pageNum, int pageSize, String keyword, String category, String kbId) {
        Page<SensitiveWord> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<SensitiveWord> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(keyword)) {
            wrapper.like(SensitiveWord::getWord, keyword);
        }
        if (StringUtils.hasText(category)) {
            wrapper.eq(SensitiveWord::getCategory, category);
        }
        if (StringUtils.hasText(kbId)) {
            wrapper.eq(SensitiveWord::getKbId, kbId);
        }
        wrapper.orderByDesc(SensitiveWord::getCreateTime);
        return sensitiveWordMapper.selectPage(page, wrapper);
    }

    public SensitiveWord save(SensitiveWord word) {
        if (word.getId() != null) {
            sensitiveWordMapper.updateById(word);
        } else {
            sensitiveWordMapper.insert(word);
        }
        invalidateCache();
        return word;
    }

    public void delete(Long id) {
        sensitiveWordMapper.deleteById(id);
        invalidateCache();
    }

    public void batchImport(List<SensitiveWord> words) {
        for (SensitiveWord word : words) {
            sensitiveWordMapper.insert(word);
        }
        invalidateCache();
    }

    public Map<String, Object> check(String text, String kbId) {
        Map<String, Object> result = new LinkedHashMap<>();
        List<String> found = new ArrayList<>();
        List<String> words = getActiveWords(kbId);

        for (String word : words) {
            if (text.contains(word)) {
                found.add(word);
            }
        }

        result.put("hasSensitive", !found.isEmpty());
        result.put("matchedWords", found);
        result.put("matchCount", found.size());
        return result;
    }

    public String filter(String text, String kbId) {
        List<String> words = getActiveWords(kbId);
        String filtered = text;
        for (String word : words) {
            filtered = filtered.replace(word, "*".repeat(word.length()));
        }
        return filtered;
    }

    private List<String> getActiveWords(String kbId) {
        if (isCacheValid()) {
            return cachedWords;
        }
        synchronized (this) {
            if (isCacheValid()) {
                return cachedWords;
            }
            cachedWords = sensitiveWordMapper.findActiveWords(kbId);
            lastCacheTime = System.currentTimeMillis();
            return cachedWords;
        }
    }

    private boolean isCacheValid() {
        return cachedWords != null && (System.currentTimeMillis() - lastCacheTime) < CACHE_TTL;
    }

    private void invalidateCache() {
        cachedWords = null;
        lastCacheTime = 0;
    }
}