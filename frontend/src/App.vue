<template>
  <div id="app">
    <ChatView />
  </div>
</template>

<script setup>
import ChatView from './components/ChatView.vue'
</script>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f5;
  color: #333;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
</style>
