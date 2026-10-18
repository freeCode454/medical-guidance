import { createApp } from 'vue'
import { createPinia } from 'pinia'
// 只引入用到的 Vant 函数式组件样式（Toast / Dialog），避免整包 200KB CSS
import 'vant/es/toast/style'
import 'vant/es/dialog/style'
import './styles/theme.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
