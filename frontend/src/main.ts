import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Element Plus 组件与样式由 unplugin 按需自动引入（见 vite.config.ts），此处不再全量引入；
// 以下为非模板用法（JS API / 指令）的样式，unplugin 无法自动注入，需手动按需引入
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/loading/style/css'
import './styles/tokens.css'
import './styles/element-override.scss'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
