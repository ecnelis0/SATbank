import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);

// The log form keeps a draft in localStorage, so without this one test's
// half-written question is restored into the next one's form. Storage is shared
// state and has to be torn down like any other.
afterEach(() => {
  window.localStorage.clear();
});
