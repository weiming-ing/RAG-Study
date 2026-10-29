<template>
  <div class="forbidden">
    <el-result icon="warning" title="403" sub-title="当前账号没有管理台访问权限，请联系管理员分配角色（ROLE_ADMIN / ROLE_KB_ADMIN）">
      <template #extra>
        <el-button type="primary" @click="$router.push('/login')">切换账号</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup>
</script>

<style scoped>
.forbidden { height: 100vh; display: flex; align-items: center; justify-content: center; }
</style>
