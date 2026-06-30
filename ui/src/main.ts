import { ElAlert } from "element-plus/es/components/alert/index.mjs";
import { ElButton } from "element-plus/es/components/button/index.mjs";
import { ElCard } from "element-plus/es/components/card/index.mjs";
import {
  ElCheckbox,
  ElCheckboxGroup,
} from "element-plus/es/components/checkbox/index.mjs";
import { ElCol } from "element-plus/es/components/col/index.mjs";
import {
  ElCollapse,
  ElCollapseItem,
} from "element-plus/es/components/collapse/index.mjs";
import {
  ElDescriptions,
  ElDescriptionsItem,
} from "element-plus/es/components/descriptions/index.mjs";
import { ElDivider } from "element-plus/es/components/divider/index.mjs";
import { ElEmpty } from "element-plus/es/components/empty/index.mjs";
import {
  ElForm,
  ElFormItem,
} from "element-plus/es/components/form/index.mjs";
import { ElInput } from "element-plus/es/components/input/index.mjs";
import { ElInputNumber } from "element-plus/es/components/input-number/index.mjs";
import { ElOption, ElSelect } from "element-plus/es/components/select/index.mjs";
import { ElRow } from "element-plus/es/components/row/index.mjs";
import { ElScrollbar } from "element-plus/es/components/scrollbar/index.mjs";
import { ElSpace } from "element-plus/es/components/space/index.mjs";
import { ElSwitch } from "element-plus/es/components/switch/index.mjs";
import { ElTabPane, ElTabs } from "element-plus/es/components/tabs/index.mjs";
import {
  ElTable,
  ElTableColumn,
} from "element-plus/es/components/table/index.mjs";
import { ElTag } from "element-plus/es/components/tag/index.mjs";
import "element-plus/dist/index.css";

import { createApp } from "vue";

import App from "./App.vue";
import "./styles.css";

const app = createApp(App);

[
  ElAlert,
  ElButton,
  ElCard,
  ElCheckbox,
  ElCheckboxGroup,
  ElCol,
  ElCollapse,
  ElCollapseItem,
  ElDescriptions,
  ElDescriptionsItem,
  ElDivider,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElRow,
  ElScrollbar,
  ElSelect,
  ElSpace,
  ElSwitch,
  ElTabPane,
  ElTable,
  ElTableColumn,
  ElTabs,
  ElTag,
].forEach((component) => {
  app.use(component);
});

app.mount("#app");
