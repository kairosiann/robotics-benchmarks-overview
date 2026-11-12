/* Offline counterpart to task_search.py. The alias vocabulary is shared. */
const TaskSearch = (() => {
  const stopWords = new Set(
    ("a an and are as at be by can could do does for from how i in into is it its " +
     "me of on onto or our robot should task that the their then them there these they " +
     "this to use using was what when where which will with would you your").split(" ")
  );
  const fields = [
    ["Task", 8, ["title", "name", "description", "instruction"]],
    ["Setup", 5, ["setup_summary", "setup", "objects"]],
    ["Grading", 4, ["grading_summary", "goal", "predicates"]],
    ["Robot input", 2, ["observation"]],
    ["Grader evidence", 2, ["grading_evidence"]],
    ["Catalog metadata", 2, ["id", "benchmark", "family", "suite", "activity", "setting", "split", "aliases", "record_kind"]],
  ];

  function textValue(value) {
    if (value === null || value === undefined) return "";
    if (Array.isArray(value)) return value.map(textValue).join(" ");
    if (typeof value === "object") {
      return Object.entries(value).map(([key, item]) => `${key} ${textValue(item)}`).join(" ");
    }
    return String(value);
  }

  function normalize(value) {
    return textValue(value)
      .replace(/([A-Z])([A-Z][a-z])/g, "$1 $2")
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .normalize("NFKD")
      .replace(/\p{Mn}/gu, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function createIndex(tasks, concepts) {
    const aliases = new Map();
    let maxAliasLength = 1;
    for (const concept of concepts) {
      const forms = [...new Set(concept.aliases.map(normalize))];
      for (const alias of forms) {
        if (!aliases.has(alias)) {
          aliases.set(alias, {term: concept.term, kind: concept.kind, aliases: forms});
        }
        maxAliasLength = Math.max(maxAliasLength, alias.split(" ").length);
      }
    }
    const records = tasks.map(task => ({
      task,
      fields: fields.map(([label, weight, keys]) => ({
        label,
        weight,
        values: keys.filter(key => task[key]).map(key => ` ${normalize(task[key])} `),
      })),
    }));
    return {aliases, maxAliasLength, records};
  }

  function queryTerms(index, query, mode) {
    const literal = normalize(query);
    const keyword = word => ({term: word, kind: "Keyword", aliases: [word], original: word});
    if (!literal) return [];
    if (mode === "exact") return [keyword(literal)];
    const terms = new Map();
    function add(item) {
      const key = item.kind + ":" + item.term;
      if (!terms.has(key)) terms.set(key, item);
    }
    for (const fragment of query.matchAll(/"([^"]*)"|([^"]+)/g)) {
      const phrase = normalize(fragment[1] ?? fragment[2]);
      if (!phrase) continue;
      if (fragment[1] !== undefined) {
        add(keyword(phrase));
        continue;
      }
      const words = phrase.split(" ");
      let offset = 0;
      while (offset < words.length) {
        let size = Math.min(index.maxAliasLength, words.length - offset);
        let alias;
        let concept;
        for (; size > 0; size--) {
          alias = words.slice(offset, offset + size).join(" ");
          concept = index.aliases.get(alias);
          if (concept) break;
        }
        if (concept) {
          add({...concept, original: alias});
        } else if (!stopWords.has(words[offset])) {
          add(keyword(words[offset]));
        }
        offset += Math.max(size, 1);
      }
    }
    return terms.size ? [...terms.values()] : [keyword(literal)];
  }

  function search(index, query = "", options = {}) {
    const {mode = "related", family = "", benchmark = "", suite = "", setting = ""} = options;
    if (!["related", "all", "exact"].includes(mode)) throw new Error("Unknown search mode: " + mode);
    const terms = queryTerms(index, query, mode);
    const phrase = normalize(query);
    const filters = [["family", family], ["benchmark", benchmark], ["setting", setting]];
    filters.push(suite.startsWith("split:") ? ["split", suite.slice(6)] : ["suite", suite]);
    const results = [];
    for (const record of index.records) {
      const {task} = record;
      if (filters.some(([key, value]) => value && (task[key] ?? "").toLowerCase() !== value.toLowerCase())) {
        continue;
      }
      const matches = [];
      let score = 0;
      for (const {term, kind, aliases, original} of terms) {
        for (const {label, weight, values} of record.fields) {
          const matched = [original, ...aliases].find(alias => values.some(value => value.includes(` ${alias} `)));
          if (!matched) continue;
          matches.push({term, kind, field: label, matched});
          const direct = matched === original || matched === original + "s" || original === matched + "s";
          const specificity = kind === "Object" || kind === "Outcome" ? 4 : 0;
          score += 20 + weight + specificity + (direct ? 3 : 0);
          break;
        }
      }
      if (terms.length && (!matches.length || (mode === "all" && matches.length !== terms.length))) {
        continue;
      }
      if (terms.length > 1 && record.fields[0].values.some(value => value.includes(` ${phrase} `))) {
        score += 6;
      }
      results.push({task, score, matches});
    }
    return results.sort((first, second) => second.score - first.score);
  }

  function describeQuery(index, query = "", mode = "related") {
    if (!["related", "all", "exact"].includes(mode)) throw new Error("Unknown search mode: " + mode);
    return queryTerms(index, query, mode).map(({term, kind, original}) => ({term, kind, original}));
  }

  return {createIndex, search, describeQuery};
})();
