import ApolloStagePage from "./apollo/page";

/**
 * The Apollo stage is the product: `/` and `/apollo` render the same tree.
 * `/ops` stays reachable for the widget grid (linked from the stage header).
 */
export default function Home() {
  return <ApolloStagePage />;
}
