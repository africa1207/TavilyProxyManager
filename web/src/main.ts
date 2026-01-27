import { createApp } from 'vue'
import App from './App.vue'
import { applyLocaleToDocument } from "./i18n";

applyLocaleToDocument();
createApp(App).mount('#app')
